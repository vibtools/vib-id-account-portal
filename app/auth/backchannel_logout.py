"""Replay-resistant OpenID Connect back-channel logout."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.sessions import SessionService
from app.auth.token_validation import OIDCValidator
from app.database.models.security import LogoutTokenReplay
from app.security.identifiers import sha256_text


class LogoutReplayError(ValueError):
    pass


async def process_logout_token(
    db: AsyncSession,
    *,
    token: str,
    validator: OIDCValidator,
    sessions: SessionService,
) -> int:
    claims = await validator.validate_logout_token(token)
    jti_hash = sha256_text(str(claims["jti"]))
    existing = (
        await db.execute(select(LogoutTokenReplay).where(LogoutTokenReplay.jti_hash == jti_hash))
    ).scalar_one_or_none()
    if existing is not None:
        raise LogoutReplayError("logout token was already processed")
    expiration = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
    db.add(LogoutTokenReplay(jti_hash=jti_hash, expires_at=expiration))
    count = await sessions.revoke_by_oidc_logout(
        db,
        sid=str(claims["sid"]) if claims.get("sid") else None,
        subject=str(claims["sub"]) if claims.get("sub") else None,
    )
    return count
