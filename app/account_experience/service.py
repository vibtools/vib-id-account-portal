"""Portable profile assembly for the Vib ID account experience API."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.account_experience.schemas import PortableProfile, PortableSocialLink
from app.accounts.repository import get_profile, list_social_links
from app.auth.sessions import AuthenticatedSession


def claims_from_bundle(token_bundle: dict[str, Any]) -> dict[str, Any]:
    claims = token_bundle.get("_id_claims", {})
    return claims if isinstance(claims, dict) else {}


def avatar_url_for_key(app_base_url: str, avatar_key: str | None) -> str | None:
    if not avatar_key:
        return None
    return f"{app_base_url.rstrip('/')}/media/profile-avatars/{avatar_key}"


async def portable_profile_for_subject(
    db: AsyncSession,
    *,
    subject: str,
    app_base_url: str,
    claims: dict[str, Any] | None = None,
) -> PortableProfile:
    profile = await get_profile(db, subject)
    social_links = await list_social_links(db, subject, include_private=False)
    claims = claims or {}
    return PortableProfile(
        subject=subject,
        display_name=(profile.display_name if profile is not None else None)
        or optional_str(claims.get("name")),
        preferred_username=optional_str(claims.get("preferred_username")),
        email=optional_str(claims.get("email")),
        email_verified=optional_bool(claims.get("email_verified")),
        preferred_language=profile.preferred_language if profile is not None else None,
        timezone=profile.timezone if profile is not None else None,
        country_code=profile.country_code if profile is not None else None,
        organization_name=profile.organization_name if profile is not None else None,
        job_title=profile.job_title if profile is not None else None,
        avatar_url=avatar_url_for_key(app_base_url, profile.avatar_key if profile else None),
        social_links=[
            PortableSocialLink(platform=item.platform, label=item.label, url=item.url)
            for item in social_links
        ],
        updated_at=profile.updated_at if profile is not None else None,
    )


async def portable_profile_for_auth(
    db: AsyncSession,
    *,
    auth: AuthenticatedSession,
    app_base_url: str,
) -> PortableProfile:
    return await portable_profile_for_subject(
        db,
        subject=auth.subject,
        app_base_url=app_base_url,
        claims=claims_from_bundle(auth.token_bundle),
    )


def optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None
