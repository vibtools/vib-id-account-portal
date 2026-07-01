from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from joserfc import jwt
from joserfc.jwk import import_key

from app.auth.oidc import OIDCClient, OIDCFlowError
from app.auth.token_validation import OIDCValidator, TokenValidationError
from app.config import get_settings
from app.security.encryption import TokenCipher


def _key_material() -> tuple[bytes, dict[str, object]]:
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
    public_jwk = import_key(public_pem, "RSA", {"kid": "test-key"}).as_dict()
    return import_key(private_pem, "RSA", {"kid": "test-key"}), public_jwk


def test_oidc_discovery_jwks_and_signed_claim_validation() -> None:
    private_key, public_jwk = _key_material()
    settings = get_settings()
    now = int(time.time())
    discovery = {
        "issuer": settings.OIDC_ISSUER_URL,
        "authorization_endpoint": "http://auth.test/authorize",
        "token_endpoint": "http://auth.test/token",
        "jwks_uri": "http://auth.test/jwks",
        "end_session_endpoint": "http://auth.test/logout",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json=discovery)
        if request.url.path == "/jwks":
            return httpx.Response(200, json={"keys": [public_jwk]})
        return httpx.Response(404)

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            validator = OIDCValidator(settings, http)
            claims = {
                "iss": settings.OIDC_ISSUER_URL,
                "sub": "user-signed",
                "aud": settings.OIDC_EXPECTED_AUDIENCE,
                "azp": settings.OIDC_CLIENT_ID,
                "exp": now + 300,
                "iat": now,
                "nonce": "nonce-1",
            }
            token = jwt.encode(
                {"alg": "RS256", "kid": "test-key"}, claims, private_key, algorithms=["RS256"]
            )
            validated = await validator.validate_id_token(token, nonce="nonce-1")
            assert validated["sub"] == "user-signed"
            with pytest.raises(TokenValidationError):
                await validator.validate_id_token(token, nonce="wrong")
            assert (await validator.metadata()).issuer == settings.OIDC_ISSUER_URL
            assert len((await validator.jwks())["keys"]) == 1

    asyncio.run(exercise())


def test_service_and_logout_claim_policy_helpers() -> None:
    assert OIDCValidator._extract_roles(
        {"realm_access": {"roles": ["role-a"]}, "scope": "role-b role-c"}
    ) == {"role-a", "role-b", "role-c"}
    OIDCValidator._validate_azp({"aud": "one"}, "client")
    with pytest.raises(TokenValidationError):
        OIDCValidator._validate_azp({"aud": ["one", "two"], "azp": "wrong"}, "client")


def test_oidc_pkce_transaction_exchange_and_replay_rejection(client) -> None:
    settings = get_settings()

    class StubValidator:
        async def metadata(self):
            from app.auth.token_validation import OIDCMetadata

            return OIDCMetadata(
                issuer=settings.OIDC_ISSUER_URL,
                authorization_endpoint="http://auth.test/authorize",
                token_endpoint="http://auth.test/token",
                jwks_uri="http://auth.test/jwks",
                end_session_endpoint=None,
            )

        async def validate_id_token(self, token: str, *, nonce: str):
            assert token == "id-token"
            assert nonce
            return {"sub": "pkce-user", "nonce": nonce, "aud": settings.OIDC_CLIENT_ID}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        assert "code_verifier=" in body
        return httpx.Response(
            200,
            content=json.dumps({"access_token": "a", "id_token": "id-token"}),
            headers={"content-type": "application/json"},
        )

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            oidc = OIDCClient(
                settings,
                http,
                StubValidator(),  # type: ignore[arg-type]
                TokenCipher(settings.TOKEN_ENCRYPTION_KEY.get_secret_value()),
            )
            async with client.app.state.database.session_factory() as db:
                location = await oidc.begin_login(db)
                await db.commit()
                assert "code_challenge_method=S256" in location
                from urllib.parse import parse_qs, urlparse

                state = parse_qs(urlparse(location).query)["state"][0]
                tokens, claims = await oidc.complete_login(db, state=state, code="code-1")
                assert tokens["access_token"] == "a"
                assert claims["sub"] == "pkce-user"
                with pytest.raises(OIDCFlowError):
                    await oidc.complete_login(db, state=state, code="code-1")

    asyncio.run(exercise())
