"""Connected-service registry models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, utcnow
from app.database.models.enums import ConnectionStatus

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class ServiceRegistry(TimestampMixin, Base):
    __tablename__ = "service_registry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    domain: Mapped[str] = mapped_column(String(253), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(280), nullable=False)
    icon_reference: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    connections: Mapped[list[UserServiceConnection]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("service_key = lower(service_key)", name="ck_service_key_lowercase"),
        CheckConstraint("sort_order >= 0", name="ck_service_sort_order"),
    )


class UserServiceConnection(Base):
    __tablename__ = "user_service_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_registry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_authenticated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    current_status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="connection_status", native_enum=False),
        nullable=False,
        default=ConnectionStatus.ACTIVE,
    )
    connection_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONVariant, nullable=False, default=dict
    )

    service: Mapped[ServiceRegistry] = relationship(back_populates="connections")

    __table_args__ = (UniqueConstraint("subject", "service_id", name="uq_user_service_connection"),)
