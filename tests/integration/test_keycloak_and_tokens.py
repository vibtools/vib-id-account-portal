from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from joserfc import jwt
from joserfc.jwk import import_key

from app.auth.keycloak_management import KeycloakManagementClient, KeycloakUnavailable
from app.auth.token_validation import OIDCMetadata, OIDCValidator, TokenValidationError
from app.config import get_settings


class MetadataValidator:
    async def metadata(self) -> OIDCMetadata:
        return OIDCMetadata(
            issuer="http://auth.test/realms/vib",
            authorization_endpoint="http://auth.test/authorize",
            token_endpoint="http://auth.test/token",
            jwks_uri="http://auth.test/jwks",
            end_session_endpoint="http://auth.test/logout",
        )


def test_keycloak_management_success_cache_and_self_only_session_lookup() -> None:
    calls: list[tuple[str, str]] = []
    authorization_headers: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path != "/token":
            authorization_headers.append(request.headers.get("authorization", ""))
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "management-token", "expires_in": 120})
        if request.url.path.endswith("/credentials"):
            return httpx.Response(200, json=[{"type": "password"}, {"type": "otp"}])
        if request.url.path.endswith("/sessions"):
            return httpx.Response(200, json=[{"id": "session-1"}, {"id": "session-2"}])
        if request.url.path.endswith("/users/user-1"):
            return httpx.Response(200, json={"enabled": True, "emailVerified": True})
        if request.url.path.endswith("/sessions/session-1"):
            return httpx.Response(204)
        if request.url.path.endswith("/logout"):
            return httpx.Response(204)
        return httpx.Response(404)

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            management = KeycloakManagementClient(
                get_settings(),
                http,
                MetadataValidator(),  # type: ignore[arg-type]
            )
            assert management.realm == "vib"
            assert management.admin_base == "http://auth.test/admin/realms/vib"
            status = await management.account_status("user-1")
            assert status.available and status.enabled and status.email_verified
            assert status.two_factor_enabled and status.session_count == 2
            assert await management.revoke_central_session("user-1", "session-1")
            assert not await management.revoke_central_session("user-1", "not-owned")
            await management.logout_user("user-1")
            assert sum(path == "/token" for _, path in calls) == 1
            assert authorization_headers
            assert all(header == "Bearer management-token" for header in authorization_headers)

    asyncio.run(exercise())


def test_keycloak_management_failure_and_circuit_breaker() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(500)
        return httpx.Response(500)

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            management = KeycloakManagementClient(
                get_settings(),
                http,
                MetadataValidator(),  # type: ignore[arg-type]
            )
            for _ in range(3):
                with pytest.raises(KeycloakUnavailable):
                    await management.logout_user("user-1")
            assert management._circuit_open_until > time.monotonic()
            unavailable = await management.account_status("user-1")
            assert not unavailable.available
            with pytest.raises(KeycloakUnavailable):
                await management.logout_user("user-1")

    asyncio.run(exercise())


def test_keycloak_management_rejects_invalid_json_responses() -> None:
    async def invalid_token_handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, text="not-json")

    async def invalid_api_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 60})
        return httpx.Response(200, text="not-json")

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(invalid_token_handler)) as http:
            management = KeycloakManagementClient(
                get_settings(),
                http,
                MetadataValidator(),  # type: ignore[arg-type]
            )
            with pytest.raises(KeycloakUnavailable):
                await management.logout_user("user-1")

        async with httpx.AsyncClient(transport=httpx.MockTransport(invalid_api_handler)) as http:
            management = KeycloakManagementClient(
                get_settings(),
                http,
                MetadataValidator(),  # type: ignore[arg-type]
            )
            with pytest.raises(KeycloakUnavailable):
                await management.logout_user("user-1")

    asyncio.run(exercise())


def _rsa_material() -> tuple[bytes, dict[str, object]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return import_key(private_pem, "RSA", {"kid": "policy-key"}), import_key(
        public_pem, "RSA", {"kid": "policy-key"}
    ).as_dict()


def test_service_and_logout_tokens_enforce_token_class_and_events() -> None:
    private_key, public_jwk = _rsa_material()
    settings = get_settings()
    now = int(time.time())
    discovery = {
        "issuer": settings.OIDC_ISSUER_URL,
        "authorization_endpoint": "http://auth.test/authorize",
        "token_endpoint": "http://auth.test/token",
        "jwks_uri": "http://auth.test/jwks",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json=discovery)
        return httpx.Response(200, json={"keys": [public_jwk]})

    def encode(claims: dict[str, object]) -> str:
        return jwt.encode(
            {"alg": "RS256", "kid": "policy-key"}, claims, private_key, algorithms=["RS256"]
        )

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            validator = OIDCValidator(settings, http)
            service_claims: dict[str, object] = {
                "iss": settings.OIDC_ISSUER_URL,
                "sub": "9a21b70d-632e-4a92-b9ca-e0e54b6cf378",
                "aud": settings.KEYCLOAK_MANAGEMENT_AUDIENCE,
                "azp": "ygit-backend",
                "preferred_username": "service-account-ygit-backend",
                "exp": now + 300,
                "iat": now,
                "scope": settings.INTERNAL_REQUIRED_ROLE,
            }
            assert (await validator.validate_service_token(encode(service_claims)))["azp"] == (
                "ygit-backend"
            )
            with pytest.raises(TokenValidationError):
                await validator.validate_service_token(
                    encode({**service_claims, "preferred_username": "normal-user"})
                )
            with pytest.raises(TokenValidationError):
                await validator.validate_service_token(
                    encode({**service_claims, "azp": "unknown-client"})
                )
            with pytest.raises(TokenValidationError):
                await validator.validate_service_token(
                    encode({**service_claims, "scope": "openid"})
                )

            event = "http://schemas.openid.net/event/backchannel-logout"
            logout_claims: dict[str, object] = {
                "iss": settings.OIDC_ISSUER_URL,
                "aud": settings.OIDC_CLIENT_ID,
                "iat": now,
                "jti": "jti-1",
                "events": {event: {}},
                "sid": "sid-1",
                "exp": now + 300,
            }
            assert (await validator.validate_logout_token(encode(logout_claims)))["sid"] == "sid-1"
            with pytest.raises(TokenValidationError):
                await validator.validate_logout_token(encode({**logout_claims, "events": {}}))
            with pytest.raises(TokenValidationError):
                await validator.validate_logout_token(encode({**logout_claims, "nonce": "bad"}))
            no_target = dict(logout_claims)
            no_target.pop("sid")
            with pytest.raises(TokenValidationError):
                await validator.validate_logout_token(encode(no_target))

    asyncio.run(exercise())


def test_discovery_and_jwks_reject_malformed_documents() -> None:
    settings = get_settings()

    async def bad_issuer(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"issuer": "http://attacker.invalid"})

    async def exercise() -> None:
        async def invalid_json(request: httpx.Request) -> httpx.Response:
            del request
            return httpx.Response(200, text="not-json")

        async with httpx.AsyncClient(transport=httpx.MockTransport(invalid_json)) as http:
            with pytest.raises(TokenValidationError):
                await OIDCValidator(settings, http).metadata()

        async with httpx.AsyncClient(transport=httpx.MockTransport(bad_issuer)) as http:
            with pytest.raises(TokenValidationError):
                await OIDCValidator(settings, http).metadata()

        async def bad_jwks(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("openid-configuration"):
                return httpx.Response(
                    200,
                    json={
                        "issuer": settings.OIDC_ISSUER_URL,
                        "authorization_endpoint": "http://auth.test/authorize",
                        "token_endpoint": "http://auth.test/token",
                        "jwks_uri": "http://auth.test/jwks",
                    },
                )
            return httpx.Response(200, json={"not_keys": []})

        async with httpx.AsyncClient(transport=httpx.MockTransport(bad_jwks)) as http:
            with pytest.raises(TokenValidationError):
                await OIDCValidator(settings, http).jwks()

        async def cross_origin_endpoint(request: httpx.Request) -> httpx.Response:
            del request
            return httpx.Response(
                200,
                json={
                    "issuer": settings.OIDC_ISSUER_URL,
                    "authorization_endpoint": "http://attacker.invalid/authorize",
                    "token_endpoint": "http://auth.test/token",
                    "jwks_uri": "http://auth.test/jwks",
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(cross_origin_endpoint)) as http:
            with pytest.raises(TokenValidationError):
                await OIDCValidator(settings, http).metadata()

    asyncio.run(exercise())
