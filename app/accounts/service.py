"""Account domain calculations."""

from __future__ import annotations

from app.database.models.account import UserProfile


def profile_completeness(profile: UserProfile | None) -> int:
    if profile is None:
        return 0
    fields = (
        profile.display_name,
        profile.phone_number,
        profile.country_code,
        profile.timezone,
        profile.preferred_language,
        profile.organization_name,
        profile.job_title,
    )
    completed = sum(bool(value) for value in fields)
    return round(completed / len(fields) * 100)
