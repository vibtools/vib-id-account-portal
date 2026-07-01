"""Session, audit, OIDC transaction, and rate-limit models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Index, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, utcnow
from app.database.models.enums import ActivityResult, ActivitySeverity

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class PortalSession(Base):
    __tablename__ = "portal_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    encrypted_token_bundle: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    user_agent_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_privacy_value: Mapped[str] = mapped_column(String(64), nullable=False)
    device_label: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(80))
    oidc_sid: Mapped[str | None] = mapped_column(String(255), index=True)

    __table_args__ = (
        Index("ix_portal_sessions_subject_active", "subject", "revoked_at", "absolute_expires_at"),
    )


class OIDCTransaction(Base):
    __tablename__ = "oidc_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    encrypted_code_verifier: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LogoutTokenReplay(Base):
    __tablename__ = "logout_token_replays"

    jti_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class SecurityActivity(Base):
    __tablename__ = "security_activity"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject: Mapped[str | None] = mapped_column(String(255), index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    event_severity: Mapped[ActivitySeverity] = mapped_column(
        Enum(ActivitySeverity, name="activity_severity", native_enum=False), nullable=False
    )
    result: Mapped[ActivityResult] = mapped_column(
        Enum(ActivityResult, name="activity_result", native_enum=False), nullable=False
    )
    request_correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_privacy_value: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    event_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONVariant, nullable=False, default=dict
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    __table_args__ = (Index("ix_security_activity_subject_occurred", "subject", "occurred_at"),)


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class MigrationLock(Base):
    __tablename__ = "migration_locks"

    lock_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
