"""OpenID Connect JWT validation through discovery and JWKS."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlparse

import httpx
from joserfc import jwt
from joserfc.errors import InvalidKeyIdError, JoseError, MissingKeyError
from joserfc.jwk import KeySet, KeySetSerialization

from app.config import Settings

ALLOWED_ALGORITHMS = ["RS256", "PS256", "ES256"]


class TokenValidationError(ValueError):
    pass


@dataclass(slots=True)
class OIDCMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    end_session_endpoint: str | None


class OIDCValidator:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client
        self._metadata: OIDCMetadata | None = None
        self._jwks: dict[str, Any] | None = None
        self._metadata_expires = 0.0
        self._jwks_expires = 0.0
        self._lock = asyncio.Lock()

    async def metadata(self, *, force: bool = False) -> OIDCMetadata:
        if self._metadata and not force and time.monotonic() < self._metadata_expires:
            return self._metadata
        async with self._lock:
            if self._metadata and not force and time.monotonic() < self._metadata_expires:
                return self._metadata
            url = f"{self.settings.OIDC_ISSUER_URL.rstrip('/')}/.well-known/openid-configuration"
            response = await self.client.get(url)
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as exc:
                raise TokenValidationError("OIDC discovery document is invalid") from exc
            if not isinstance(payload, dict):
                raise TokenValidationError("OIDC discovery document is invalid")
            if payload.get("issuer") != self.settings.OIDC_ISSUER_URL:
                raise TokenValidationError("OIDC discovery issuer mismatch")
            endpoint_names = ("authorization_endpoint", "token_endpoint", "jwks_uri")
            endpoints: dict[str, str] = {}
            for name in endpoint_names:
                value = payload.get(name)
                if not isinstance(value, str):
                    raise TokenValidationError("OIDC discovery endpoint is invalid")
                self._validate_provider_endpoint(value)
                endpoints[name] = value
            end_session = payload.get("end_session_endpoint")
            if end_session is not None:
                if not isinstance(end_session, str):
                    raise TokenValidationError("OIDC discovery endpoint is invalid")
                self._validate_provider_endpoint(end_session)
            metadata = OIDCMetadata(
                issuer=str(payload["issuer"]),
                authorization_endpoint=endpoints["authorization_endpoint"],
                token_endpoint=endpoints["token_endpoint"],
                jwks_uri=endpoints["jwks_uri"],
                end_session_endpoint=end_session,
            )
            self._metadata = metadata
            self._metadata_expires = time.monotonic() + 300
            return metadata

    def _validate_provider_endpoint(self, value: str) -> None:
        issuer = urlparse(self.settings.OIDC_ISSUER_URL)
        endpoint = urlparse(value)
        if (
            endpoint.scheme != issuer.scheme
            or endpoint.hostname != issuer.hostname
            or endpoint.username is not None
            or endpoint.password is not None
        ):
            raise TokenValidationError("OIDC discovery endpoint origin mismatch")

    async def jwks(self, *, force: bool = False) -> dict[str, Any]:
        if self._jwks and not force and time.monotonic() < self._jwks_expires:
            return self._jwks
        metadata = await self.metadata()
        async with self._lock:
            if self._jwks and not force and time.monotonic() < self._jwks_expires:
                return self._jwks
            response = await self.client.get(metadata.jwks_uri)
            response.raise_for_status()
            raw_payload = response.json()
            if not isinstance(raw_payload, dict):
                raise TokenValidationError("OIDC JWKS is invalid")
            payload: dict[str, Any] = raw_payload
            if not isinstance(payload.get("keys"), list):
                raise TokenValidationError("OIDC JWKS is invalid")
            self._jwks = payload
            self._jwks_expires = time.monotonic() + 300
            return payload

    async def validate_id_token(self, token: str, *, nonce: str) -> dict[str, Any]:
        claims = await self._decode(
            token,
            audience=self.settings.OIDC_EXPECTED_AUDIENCE,
            required_claims={"iss", "sub", "aud", "exp", "iat", "nonce"},
        )
        if claims.get("nonce") != nonce:
            raise TokenValidationError("ID token nonce mismatch")
        self._validate_azp(claims, self.settings.OIDC_CLIENT_ID)
        return claims

    async def validate_logout_token(self, token: str) -> dict[str, Any]:
        claims = await self._decode(
            token,
            audience=self.settings.OIDC_CLIENT_ID,
            required_claims={"iss", "aud", "iat", "jti", "events"},
        )
        events = claims.get("events")
        logout_event = "http://schemas.openid.net/event/backchannel-logout"
        if not isinstance(events, dict) or logout_event not in events:
            raise TokenValidationError("logout token event is invalid")
        if "nonce" in claims:
            raise TokenValidationError("logout token must not contain nonce")
        if not claims.get("sid") and not claims.get("sub"):
            raise TokenValidationError("logout token requires sid or sub")
        return claims

    async def validate_service_token(self, token: str) -> dict[str, Any]:
        claims = await self._decode(
            token,
            audience=self.settings.KEYCLOAK_MANAGEMENT_AUDIENCE,
            required_claims={
                "iss",
                "sub",
                "aud",
                "exp",
                "iat",
                "azp",
                "preferred_username",
            },
        )
        azp = str(claims.get("azp", ""))
        if azp not in self.settings.allowed_internal_clients:
            raise TokenValidationError("service client is not allowlisted")
        roles = self._extract_roles(claims)
        if self.settings.INTERNAL_REQUIRED_ROLE not in roles:
            raise TokenValidationError("required internal role is absent")
        expected_service_username = f"service-account-{azp}"
        if claims.get("preferred_username") != expected_service_username:
            raise TokenValidationError("end-user access token is not accepted")
        return claims

    async def _decode(
        self,
        token: str,
        *,
        audience: str,
        required_claims: set[str],
    ) -> dict[str, Any]:
        keys = await self.jwks()
        try:
            result = self._decode_with_keys(token, keys, audience)
        except (InvalidKeyIdError, MissingKeyError):
            keys = await self.jwks(force=True)
            try:
                result = self._decode_with_keys(token, keys, audience)
            except JoseError as exc:
                raise TokenValidationError("JWT validation failed") from exc
        except JoseError as exc:
            raise TokenValidationError("JWT validation failed") from exc
        missing = required_claims.difference(result)
        if missing:
            raise TokenValidationError("JWT required claims are absent")
        return result

    def _decode_with_keys(self, token: str, keys: dict[str, Any], audience: str) -> dict[str, Any]:
        key_set = KeySet.import_key_set(cast(KeySetSerialization, keys))
        decoded = jwt.decode(token, key_set, algorithms=ALLOWED_ALGORITHMS)
        claims = dict(decoded.claims)
        registry = jwt.JWTClaimsRegistry(
            leeway=self.settings.OIDC_CLOCK_SKEW_SECONDS,
            iss={"essential": True, "value": self.settings.OIDC_ISSUER_URL},
            aud={"essential": True, "value": audience},
            exp={"essential": True},
            iat={"essential": True},
            nbf={"essential": False},
        )
        registry.validate(claims)
        return claims

    @staticmethod
    def _validate_azp(claims: dict[str, Any], expected: str) -> None:
        audience = claims.get("aud")
        if isinstance(audience, list) and len(audience) > 1 and claims.get("azp") != expected:
            raise TokenValidationError("ID token authorized party mismatch")
        if claims.get("azp") not in (None, expected):
            raise TokenValidationError("ID token authorized party mismatch")

    @staticmethod
    def _extract_roles(claims: dict[str, Any]) -> set[str]:
        roles: set[str] = set()
        realm_access = claims.get("realm_access")
        if isinstance(realm_access, dict) and isinstance(realm_access.get("roles"), list):
            roles.update(str(role) for role in realm_access["roles"])
        scope = claims.get("scope")
        if isinstance(scope, str):
            roles.update(scope.split())
        return roles
