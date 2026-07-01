from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database.models.security import LogoutTokenReplay, PortalSession, SecurityActivity


def test_backchannel_logout_is_replay_resistant(client, login_user) -> None:
    login_user(subject="logout-user", oidc_sid="central-session-1")
    first = client.post("/auth/backchannel-logout", data={"logout_token": "valid-logout-token"})
    assert first.status_code == 200
    second = client.post("/auth/backchannel-logout", data={"logout_token": "valid-logout-token"})
    assert second.status_code == 400

    async def inspect() -> tuple[int, bool]:
        async with client.app.state.database.session_factory() as db:
            replay_count = len(list((await db.execute(select(LogoutTokenReplay))).scalars()))
            session = (await db.execute(select(PortalSession))).scalar_one()
            return replay_count, session.revoked_at is not None

    replay_count, revoked = asyncio.run(inspect())
    assert replay_count == 1
    assert revoked


def test_xss_sql_injection_and_control_input_are_rejected_or_escaped(client, login_user) -> None:
    login = login_user(subject="security-user")

    async def version() -> str:
        from app.database.models.account import UserProfile

        async with client.app.state.database.session_factory() as db:
            profile = (await db.execute(select(UserProfile))).scalar_one()
            return profile.updated_at.isoformat()

    response = client.post(
        "/profile",
        data={
            "csrf_token": login.csrf_token,
            "display_name": "<script>alert(1)</script>",
            "timezone": "UTC",
            "preferred_language": "en",
            "version": asyncio.run(version()),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get("/profile")
    assert "<script>alert(1)</script>" not in page.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page.text
    control = client.post(
        "/profile/contacts",
        data={
            "csrf_token": login.csrf_token,
            "contact_type": "other",
            "label": "bad\x00label",
            "value": "x' OR 1=1 --",
        },
    )
    assert control.status_code == 422


def test_expired_session_cookie_does_not_authenticate(client, login_user) -> None:
    login = login_user(subject="expired-user")

    async def expire() -> None:
        async with client.app.state.database.session_factory() as db:
            session = (
                await db.execute(select(PortalSession).where(PortalSession.id == login.session_id))
            ).scalar_one()
            session.idle_expires_at = datetime.now(UTC) - timedelta(minutes=1)
            await db.commit()

    asyncio.run(expire())
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_sensitive_values_never_written_to_activity(client, login_user) -> None:
    login_user(subject="audit-user")

    async def inspect() -> None:
        async with client.app.state.database.session_factory() as db:
            activities = list((await db.execute(select(SecurityActivity))).scalars())
            serialized = repr([activity.event_metadata for activity in activities])
            assert "server-only-access-token" not in serialized
            assert "server-only-refresh-token" not in serialized

    asyncio.run(inspect())
