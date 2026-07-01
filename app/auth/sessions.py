"""Server-side opaque session lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.base import as_utc
from app.database.models.security import PortalSession
from app.security.encryption import TokenCipher
from app.security.identifiers import (
    device_label,
    generate_opaque_token,
    privacy_ip,
    sanitize_user_agent,
    sha256_text,
)


@dataclass(slots=True)
class AuthenticatedSession:
    model: PortalSession
    raw_id: str
    token_bundle: dict[str, Any]
    subject_id: str

    @property
    def subject(self) -> str:
        return self.subject_id


class SessionService:
    def __init__(self, settings: Settings, cipher: TokenCipher) -> None:
        self.settings = settings
        self.cipher = cipher

    async def create(
        self,
        db: AsyncSession,
        *,
        subject: str,
        token_bundle: dict[str, Any],
        user_agent: str | None,
        ip_address: str | None,
        oidc_sid: str | None,
    ) -> AuthenticatedSession:
        raw_id = generate_opaque_token(32)
        now = datetime.now(UTC)
        summary = sanitize_user_agent(user_agent)
        model = PortalSession(
            session_hash=sha256_text(raw_id),
            subject=subject,
            encrypted_token_bundle=self.cipher.encrypt_json(token_bundle),
            user_agent_summary=summary,
            ip_privacy_value=privacy_ip(
                ip_address, self.settings.IP_PRIVACY_KEY.get_secret_value()
            ),
            device_label=device_label(summary),
            created_at=now,
            last_seen_at=now,
            idle_expires_at=now + timedelta(minutes=self.settings.SESSION_IDLE_MINUTES),
            absolute_expires_at=now + timedelta(hours=self.settings.SESSION_ABSOLUTE_HOURS),
            oidc_sid=oidc_sid,
        )
        db.add(model)
        await db.flush()
        await self._enforce_concurrent_limit(db, subject, keep=model.id)
        return AuthenticatedSession(
            model=model,
            raw_id=raw_id,
            token_bundle=token_bundle,
            subject_id=subject,
        )

    async def resolve(
        self,
        db: AsyncSession,
        raw_id: str | None,
        *,
        touch: bool = True,
    ) -> AuthenticatedSession | None:
        if not raw_id:
            return None
        now = datetime.now(UTC)
        statement = select(PortalSession).where(PortalSession.session_hash == sha256_text(raw_id))
        model = (await db.execute(statement)).scalar_one_or_none()
        if (
            model is None
            or model.revoked_at is not None
            or as_utc(model.idle_expires_at) <= now
            or as_utc(model.absolute_expires_at) <= now
        ):
            if model is not None and model.revoked_at is None:
                model.revoked_at = now
                model.revocation_reason = "expired"
                await db.flush()
            return None
        if touch and (now - as_utc(model.last_seen_at)) >= timedelta(seconds=60):
            model.last_seen_at = now
            model.idle_expires_at = min(
                now + timedelta(minutes=self.settings.SESSION_IDLE_MINUTES),
                as_utc(model.absolute_expires_at),
            )
            await db.flush()
        return AuthenticatedSession(
            model=model,
            raw_id=raw_id,
            token_bundle=self.cipher.decrypt_json(model.encrypted_token_bundle),
            subject_id=model.subject,
        )

    async def revoke(
        self,
        db: AsyncSession,
        *,
        session_id: object,
        subject: str,
        reason: str,
    ) -> bool:
        statement = select(PortalSession).where(
            PortalSession.id == session_id,
            PortalSession.subject == subject,
            PortalSession.revoked_at.is_(None),
        )
        model = (await db.execute(statement)).scalar_one_or_none()
        if model is None:
            return False
        model.revoked_at = datetime.now(UTC)
        model.revocation_reason = reason[:80]
        await db.flush()
        return True

    async def revoke_all_other(
        self,
        db: AsyncSession,
        *,
        subject: str,
        current_id: object,
    ) -> int:
        now = datetime.now(UTC)
        result = await db.execute(
            update(PortalSession)
            .where(
                PortalSession.subject == subject,
                PortalSession.id != current_id,
                PortalSession.revoked_at.is_(None),
            )
            .values(revoked_at=now, revocation_reason="user-revoked-all-others")
        )
        return int(cast(CursorResult[Any], result).rowcount or 0)

    async def revoke_by_oidc_logout(
        self,
        db: AsyncSession,
        *,
        sid: str | None,
        subject: str | None,
    ) -> int:
        if not sid and not subject:
            return 0
        conditions = []
        if sid:
            conditions.append(PortalSession.oidc_sid == sid)
        if subject:
            conditions.append(PortalSession.subject == subject)
        now = datetime.now(UTC)
        result = await db.execute(
            update(PortalSession)
            .where(*conditions, PortalSession.revoked_at.is_(None))
            .values(revoked_at=now, revocation_reason="oidc-backchannel-logout")
        )
        return int(cast(CursorResult[Any], result).rowcount or 0)

    async def list_active(self, db: AsyncSession, subject: str) -> list[PortalSession]:
        now = datetime.now(UTC)
        statement = (
            select(PortalSession)
            .where(
                PortalSession.subject == subject,
                PortalSession.revoked_at.is_(None),
                PortalSession.idle_expires_at > now,
                PortalSession.absolute_expires_at > now,
            )
            .order_by(PortalSession.last_seen_at.desc())
            .limit(50)
        )
        return list((await db.execute(statement)).scalars())

    async def _enforce_concurrent_limit(
        self, db: AsyncSession, subject: str, *, keep: object
    ) -> None:
        statement = (
            select(PortalSession)
            .where(
                PortalSession.subject == subject,
                PortalSession.revoked_at.is_(None),
                PortalSession.id != keep,
            )
            .order_by(PortalSession.last_seen_at.desc())
        )
        sessions = list((await db.execute(statement)).scalars())
        allowed_others = max(0, self.settings.SESSION_MAX_CONCURRENT - 1)
        for old in sessions[allowed_others:]:
            old.revoked_at = datetime.now(UTC)
            old.revocation_reason = "concurrent-session-limit"
        await db.flush()
