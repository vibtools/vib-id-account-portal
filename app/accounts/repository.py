"""Account persistence operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.schemas import ContactCreate, ProfileUpdate
from app.database.base import as_utc
from app.database.locks import acquire_advisory_xact_lock
from app.database.models.account import UserContact, UserPreference, UserProfile
from app.database.models.enums import Theme


class ConcurrentProfileUpdate(RuntimeError):
    pass


async def ensure_account_records(
    db: AsyncSession,
    *,
    subject: str,
    display_name: str,
    locale: str = "en",
) -> tuple[UserProfile, UserPreference]:
    await acquire_advisory_xact_lock(
        db,
        namespace="account-bootstrap",
        identity=subject,
    )
    profile = (
        await db.execute(select(UserProfile).where(UserProfile.subject == subject))
    ).scalar_one_or_none()
    if profile is None:
        profile = UserProfile(
            subject=subject,
            display_name=display_name[:120] or "Vib ID user",
            preferred_language=locale[:16],
            timezone="UTC",
        )
        db.add(profile)
    preferences = (
        await db.execute(select(UserPreference).where(UserPreference.subject == subject))
    ).scalar_one_or_none()
    if preferences is None:
        preferences = UserPreference(subject=subject, locale=locale[:16], timezone="UTC")
        db.add(preferences)
    await db.flush()
    return profile, preferences


async def get_profile(db: AsyncSession, subject: str) -> UserProfile | None:
    return (
        await db.execute(select(UserProfile).where(UserProfile.subject == subject))
    ).scalar_one_or_none()


async def update_profile(
    db: AsyncSession,
    *,
    subject: str,
    payload: ProfileUpdate,
) -> UserProfile:
    profile = (
        await db.execute(
            select(UserProfile).where(UserProfile.subject == subject).with_for_update()
        )
    ).scalar_one_or_none()
    if profile is None:
        raise LookupError("profile does not exist")
    current = as_utc(profile.updated_at)
    supplied = payload.version.astimezone(UTC)
    if current != supplied:
        raise ConcurrentProfileUpdate("profile changed in another request")
    for field in (
        "display_name",
        "phone_number",
        "phone_country_code",
        "country_code",
        "timezone",
        "preferred_language",
        "organization_name",
        "job_title",
    ):
        setattr(profile, field, getattr(payload, field))
    profile.updated_at = datetime.now(UTC)
    await db.flush()
    return profile


async def list_contacts(db: AsyncSession, subject: str) -> list[UserContact]:
    result = await db.execute(
        select(UserContact)
        .where(UserContact.subject == subject)
        .order_by(UserContact.contact_type, UserContact.is_primary.desc(), UserContact.created_at)
    )
    return list(result.scalars())


async def add_contact(
    db: AsyncSession,
    *,
    subject: str,
    payload: ContactCreate,
    contact_limit: int,
) -> UserContact:
    count = await db.scalar(
        select(func.count(UserContact.id)).where(UserContact.subject == subject)
    )
    if int(count or 0) >= contact_limit:
        raise ValueError("Contact limit reached")
    normalized = payload.normalized()
    if payload.is_primary:
        existing_primary = (
            await db.execute(
                select(UserContact).where(
                    UserContact.subject == subject,
                    UserContact.contact_type == payload.contact_type,
                    UserContact.is_primary.is_(True),
                )
            )
        ).scalar_one_or_none()
        if existing_primary is not None:
            existing_primary.is_primary = False
    contact = UserContact(
        subject=subject,
        contact_type=payload.contact_type,
        label=payload.label,
        value=payload.value,
        normalized_value=normalized,
        is_primary=payload.is_primary,
        is_verified=False,
    )
    db.add(contact)
    await db.flush()
    return contact


async def delete_contact(db: AsyncSession, *, subject: str, contact_id: object) -> bool:
    result = await db.execute(
        delete(UserContact).where(
            UserContact.id == contact_id,
            UserContact.subject == subject,
        )
    )
    return bool(cast(CursorResult[Any], result).rowcount)


async def get_preferences(db: AsyncSession, subject: str) -> UserPreference | None:
    return (
        await db.execute(select(UserPreference).where(UserPreference.subject == subject))
    ).scalar_one_or_none()


async def update_preferences(
    db: AsyncSession,
    *,
    subject: str,
    theme: Theme,
    locale: str,
    timezone_name: str,
    security_notifications: bool,
) -> UserPreference:
    preference = await get_preferences(db, subject)
    if preference is None:
        preference = UserPreference(subject=subject)
        db.add(preference)
    preference.theme = theme
    preference.locale = locale
    preference.timezone = timezone_name
    preference.security_email_notifications = security_notifications
    await db.flush()
    return preference
