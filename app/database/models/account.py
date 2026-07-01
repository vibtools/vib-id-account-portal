"""Account profile and preference models."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin
from app.database.models.enums import ContactType, Theme


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(32))
    phone_country_code: Mapped[str | None] = mapped_column(String(8))
    country_code: Mapped[str | None] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    preferred_language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    organization_name: Mapped[str | None] = mapped_column(String(160))
    job_title: Mapped[str | None] = mapped_column(String(120))
    avatar_key: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        CheckConstraint("length(subject) >= 3", name="ck_user_profiles_subject_length"),
        CheckConstraint("country_code IS NULL OR length(country_code) = 2", name="ck_country_code"),
    )


class UserContact(TimestampMixin, Base):
    __tablename__ = "user_contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact_type: Mapped[ContactType] = mapped_column(
        Enum(ContactType, name="contact_type", native_enum=False), nullable=False
    )
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "subject", "contact_type", "normalized_value", name="uq_contact_subject_type_value"
        ),
        Index(
            "uq_contact_primary_per_type",
            "subject",
            "contact_type",
            unique=True,
            postgresql_where=text("is_primary"),
            sqlite_where=text("is_primary = 1"),
        ),
    )


class UserPreference(TimestampMixin, Base):
    __tablename__ = "user_preferences"

    subject: Mapped[str] = mapped_column(String(255), primary_key=True)
    theme: Mapped[Theme] = mapped_column(
        Enum(Theme, name="theme", native_enum=False), nullable=False, default=Theme.SYSTEM
    )
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    security_email_notifications: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    product_announcements: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
