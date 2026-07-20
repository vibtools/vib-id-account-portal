"""Account persistence operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.schemas import ContactCreate, ProfileUpdate, SocialLinkPayload
from app.database.base import as_utc
from app.database.locks import acquire_advisory_xact_lock
from app.database.models.account import (
    UserContact,
    UserPreference,
    UserProfile,
    UserProfilePhoto,
    UserSocialLink,
)
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
        preferences = UserPreference(
            subject=subject,
            theme=Theme.DARK,
            locale=locale[:16],
            timezone="UTC",
        )
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
    supplied = as_utc(payload.version)
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
        preference = UserPreference(subject=subject, theme=Theme.DARK)
        db.add(preference)
    preference.theme = theme
    preference.locale = locale
    preference.timezone = timezone_name
    preference.security_email_notifications = security_notifications
    await db.flush()
    return preference



async def list_social_links(
    db: AsyncSession, subject: str, *, include_private: bool = True
) -> list[UserSocialLink]:
    statement = select(UserSocialLink).where(UserSocialLink.subject == subject)
    if not include_private:
        statement = statement.where(UserSocialLink.visibility == "apps")
    result = await db.execute(statement.order_by(UserSocialLink.platform))
    return list(result.scalars())


async def upsert_social_link(
    db: AsyncSession, *, subject: str, payload: SocialLinkPayload
) -> UserSocialLink:
    link = (
        await db.execute(
            select(UserSocialLink).where(
                UserSocialLink.subject == subject, UserSocialLink.platform == payload.platform
            )
        )
    ).scalar_one_or_none()
    if link is None:
        link = UserSocialLink(subject=subject, platform=payload.platform)
        db.add(link)
    link.label = payload.label
    link.url = payload.url
    link.normalized_url = payload.normalized()
    link.visibility = payload.visibility
    await db.flush()
    return link


async def delete_social_link(db: AsyncSession, *, subject: str, link_id: object) -> bool:
    result = await db.execute(
        delete(UserSocialLink).where(
            UserSocialLink.id == link_id, UserSocialLink.subject == subject
        )
    )
    return bool(cast(CursorResult[Any], result).rowcount)


async def get_profile_photo(db: AsyncSession, *, subject: str) -> UserProfilePhoto | None:
    return (
        await db.execute(select(UserProfilePhoto).where(UserProfilePhoto.subject == subject))
    ).scalar_one_or_none()


async def get_profile_photo_by_key(db: AsyncSession, *, avatar_key: str) -> UserProfilePhoto | None:
    return (
        await db.execute(select(UserProfilePhoto).where(UserProfilePhoto.avatar_key == avatar_key))
    ).scalar_one_or_none()


async def upsert_profile_photo(
    db: AsyncSession,
    *,
    subject: str,
    avatar_key: str,
    mime_type: str,
    size_bytes: int,
    sha256_hash: str,
    image_bytes: bytes,
) -> UserProfilePhoto:
    photo = await get_profile_photo(db, subject=subject)
    if photo is None:
        photo = UserProfilePhoto(subject=subject, avatar_key=avatar_key)
        db.add(photo)
    photo.avatar_key = avatar_key
    photo.mime_type = mime_type
    photo.size_bytes = size_bytes
    photo.sha256_hash = sha256_hash
    photo.image_bytes = image_bytes
    profile = await get_profile(db, subject)
    if profile is not None:
        profile.avatar_key = avatar_key
    await db.flush()
    return photo


async def delete_profile_photo(db: AsyncSession, *, subject: str) -> bool:
    profile = await get_profile(db, subject)
    if profile is not None:
        profile.avatar_key = None
    result = await db.execute(delete(UserProfilePhoto).where(UserProfilePhoto.subject == subject))
    return bool(cast(CursorResult[Any], result).rowcount)
