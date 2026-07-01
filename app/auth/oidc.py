"""OIDC Authorization Code + PKCE S256 flow implementation."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token_validation import OIDCValidator
from app.config import Settings
from app.database.base import as_utc
from app.database.models.security import OIDCTransaction
from app.security.encryption import TokenCipher
from app.security.identifiers import generate_opaque_token, sha256_text


class OIDCFlowError(ValueError):
    pass


class OIDCClient:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        validator: OIDCValidator,
        cipher: TokenCipher,
    ) -> None:
        self.settings = settings
        self.client = client
        self.validator = validator
        self.cipher = cipher

    async def begin_login(self, db: AsyncSession) -> str:
        state = generate_opaque_token(32)
        nonce = generate_opaque_token(32)
        verifier = secrets.token_urlsafe(64)
        challenge = create_s256_code_challenge(verifier)
        now = datetime.now(UTC)
        db.add(
            OIDCTransaction(
                state_hash=sha256_text(state),
                encrypted_code_verifier=self.cipher.encrypt_bytes(verifier.encode("ascii")),
                nonce=nonce,
                created_at=now,
                expires_at=now + timedelta(minutes=10),
            )
        )
        await db.flush()
        metadata = await self.validator.metadata()
        params = {
            "client_id": self.settings.OIDC_CLIENT_ID,
            "response_type": "code",
            "scope": self.settings.OIDC_SCOPES,
            "redirect_uri": self.settings.OIDC_REDIRECT_URI,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{metadata.authorization_endpoint}?{urlencode(params)}"

    async def complete_login(
        self,
        db: AsyncSession,
        *,
        state: str,
        code: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        now = datetime.now(UTC)
        statement = (
            select(OIDCTransaction)
            .where(OIDCTransaction.state_hash == sha256_text(state))
            .with_for_update()
        )
        transaction = (await db.execute(statement)).scalar_one_or_none()
        if (
            transaction is None
            or transaction.consumed_at is not None
            or as_utc(transaction.expires_at) <= now
        ):
            raise OIDCFlowError("OIDC transaction is invalid or expired")
        transaction.consumed_at = now
        verifier = self.cipher.decrypt_bytes(transaction.encrypted_code_verifier).decode("ascii")
        metadata = await self.validator.metadata()
        response = await self.client.post(
            metadata.token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.OIDC_REDIRECT_URI,
                "client_id": self.settings.OIDC_CLIENT_ID,
                "client_secret": self.settings.OIDC_CLIENT_SECRET.get_secret_value(),
                "code_verifier": verifier,
            },
            headers={"Accept": "application/json"},
        )
        if response.status_code != 200:
            raise OIDCFlowError("OIDC token exchange failed")
        raw_token_bundle = response.json()
        if not isinstance(raw_token_bundle, dict):
            raise OIDCFlowError("OIDC token response is invalid")
        token_bundle: dict[str, Any] = raw_token_bundle
        id_token = token_bundle.get("id_token")
        if not isinstance(id_token, str):
            raise OIDCFlowError("OIDC response did not include an ID token")
        claims = await self.validator.validate_id_token(id_token, nonce=transaction.nonce)
        return token_bundle, claims

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        metadata = await self.validator.metadata()
        response = await self.client.post(
            metadata.token_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.settings.OIDC_CLIENT_ID,
                "client_secret": self.settings.OIDC_CLIENT_SECRET.get_secret_value(),
            },
            headers={"Accept": "application/json"},
        )
        if response.status_code != 200:
            raise OIDCFlowError("OIDC refresh failed")
        raw_payload = response.json()
        if not isinstance(raw_payload, dict):
            raise OIDCFlowError("OIDC refresh response is invalid")
        payload: dict[str, Any] = raw_payload
        if not isinstance(payload.get("access_token"), str):
            raise OIDCFlowError("OIDC refresh response is invalid")
        if "refresh_token" not in payload:
            payload["refresh_token"] = refresh_token
        return payload
