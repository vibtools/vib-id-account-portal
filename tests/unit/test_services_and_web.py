from __future__ import annotations

from datetime import UTC, datetime

import pytest
from starlette.requests import Request

from app.account_security.service import application_summaries
from app.accounts.service import profile_completeness
from app.database.models.account import UserProfile
from app.services_registry.service import validate_service_metadata
from app.web import base_context, format_datetime


def test_profile_completeness_progresses() -> None:
    assert profile_completeness(None) == 0
    profile = UserProfile(subject="abc", display_name="Name")
    assert 0 < profile_completeness(profile) < 100
    profile.phone_number = "+8801712345678"
    profile.country_code = "BD"
    profile.timezone = "UTC"
    profile.preferred_language = "en"
    profile.organization_name = "Vib Tools"
    profile.job_title = "Developer"
    assert profile_completeness(profile) == 100


def test_service_metadata_validation() -> None:
    validate_service_metadata(
        service_key="ygit-net",
        display_name="YGit",
        domain="ygit.net",
        description="Git service",
        icon_reference="icons/ygit.svg",
        sort_order=1,
    )
    with pytest.raises(ValueError):
        validate_service_metadata(
            service_key="BAD",
            display_name="YGit",
            domain="https://ygit.net/path",
            description="Git service",
            icon_reference="../secret",
            sort_order=-1,
        )


def test_datetime_filter_handles_timezone_and_none() -> None:
    assert format_datetime(None) == "Not available"
    rendered = format_datetime(datetime(2026, 6, 30, 0, 0, tzinfo=UTC), "Asia/Dhaka")
    assert rendered.startswith("2026-06-30 06:00")
    fallback = format_datetime(datetime(2026, 6, 30, tzinfo=UTC), "Invalid/Zone")
    assert fallback.endswith("UTC")


def test_base_context_has_no_raw_token_fields(client, login_user) -> None:
    auth_result = login_user()

    async def resolve():
        async with client.app.state.database.session_factory() as db:
            return await client.app.state.session_service.resolve(db, auth_result.raw_session_id)

    import asyncio

    auth = asyncio.run(resolve())
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1),
        "scheme": "http",
        "app": client.app,
    }
    request = Request(scope)
    context = base_context(request, auth=auth)
    assert context["claims"]["sub"] == "user-123"
    assert context["csrf_token"]
    assert "access_token" not in context



def test_application_summaries_support_central_session_candidates(client, login_user) -> None:
    login = login_user(subject="central-candidates-user")

    async def run() -> list[str]:
        async with client.app.state.database.session_factory() as db:
            apps = await application_summaries(
                db,
                login.subject,
                central_sessions=[
                    {
                        "clients": {"uuid-like": "YGIT", "ygit-dev": "YGIT Dev"},
                        "lastAccess": 1000,
                    },
                    {"clients": ["ygit-net", "unknown-client"], "lastAccess": 1_771_432_800_000},
                ],
            )
            return [item.service_key for item in apps]

    import asyncio

    keys = asyncio.run(run())
    assert "ygit" in keys
    assert "ygit-dev" in keys
