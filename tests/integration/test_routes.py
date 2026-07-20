from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select

from app.database.models.account import UserContact, UserProfile
from app.database.models.service import ServiceRegistry


def test_public_login_callback_and_security_headers(client) -> None:
    class FakeOIDC:
        async def begin_login(self, db):
            del db
            return "http://auth.test/authorize?state=opaque&code_challenge_method=S256"

        async def complete_login(self, db, *, state: str, code: str):
            del db
            assert state == "state-1"
            assert code == "code-1"
            return (
                {"access_token": "a", "refresh_token": "r", "id_token": "i"},
                {
                    "sub": "callback-user",
                    "name": "Callback User",
                    "email": "callback@example.test",
                    "email_verified": True,
                    "sid": "sid-callback",
                },
            )

    client.app.state.oidc = FakeOIDC()
    login = client.get("/login", follow_redirects=False)
    assert login.status_code == 302
    assert login.headers["location"].startswith("http://auth.test/authorize")
    callback = client.get("/auth/callback?state=state-1&code=code-1", follow_redirects=False)
    assert callback.status_code == 303
    assert callback.headers["location"] == "/"
    assert "HttpOnly" in callback.headers["set-cookie"]
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Callback User" in dashboard.text
    assert "default-src 'self'" in dashboard.headers["content-security-policy"]
    assert dashboard.headers["cache-control"].startswith("no-store")
    assert dashboard.headers["x-content-type-options"] == "nosniff"
    failed = client.get("/auth/callback?error=access_denied", follow_redirects=False)
    assert failed.status_code == 303
    assert failed.headers["location"] == "/auth/error"


def test_all_authenticated_pages_and_no_token_disclosure(client, login_user) -> None:
    login_user(email_verified=False)
    for path in (
        "/",
        "/profile",
        "/security",
        "/sessions",
        "/services",
        "/activity",
        "/preferences",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "server-only-access-token" not in response.text
        assert "server-only-refresh-token" not in response.text
    services = client.get("/services")
    assert "Disconnect service" not in services.text
    assert "client secret" not in services.text.lower()
    assert "/services/" not in services.text or "static/icons" in services.text


def test_profile_contact_preferences_activity_and_idor(client, login_user) -> None:
    login = login_user()

    async def profile_version() -> str:
        async with client.app.state.database.session_factory() as db:
            profile = (
                await db.execute(select(UserProfile).where(UserProfile.subject == login.subject))
            ).scalar_one()
            return profile.updated_at.isoformat()

    version = asyncio.run(profile_version())
    bad_csrf = client.post("/preferences", data={"csrf_token": "wrong"})
    assert bad_csrf.status_code == 403
    updated = client.post(
        "/profile",
        data={
            "csrf_token": login.csrf_token,
            "display_name": "Updated User",
            "phone_number": "1712345678",
            "phone_country_code": "+880",
            "country_code": "BD",
            "timezone": "Asia/Dhaka",
            "preferred_language": "bn-BD",
            "organization_name": "Vib Tools",
            "job_title": "Lead Developer",
            "version": version,
        },
        follow_redirects=False,
    )
    assert updated.status_code == 303
    contact = client.post(
        "/profile/contacts",
        data={
            "csrf_token": login.csrf_token,
            "contact_type": "email",
            "label": "Work",
            "value": "User@Example.com",
            "is_primary": "on",
        },
        follow_redirects=False,
    )
    assert contact.status_code == 303
    preference = client.post(
        "/preferences",
        data={
            "csrf_token": login.csrf_token,
            "theme": "dark",
            "locale": "bn-BD",
            "timezone": "Asia/Dhaka",
            "security_notifications": "on",
        },
        follow_redirects=False,
    )
    assert preference.status_code == 303

    async def inspect_and_seed_other() -> tuple[str, str]:
        async with client.app.state.database.session_factory() as db:
            saved_contact = (
                await db.execute(select(UserContact).where(UserContact.subject == login.subject))
            ).scalar_one()
            other = UserContact(
                subject="other-user",
                contact_type=saved_contact.contact_type,
                label="Other",
                value="other@example.com",
                normalized_value="other@example.com",
                is_primary=False,
                is_verified=False,
            )
            db.add(other)
            await db.commit()
            return str(saved_contact.id), str(other.id)

    own_contact_id, other_contact_id = asyncio.run(inspect_and_seed_other())
    denied = client.post(
        f"/profile/contacts/{other_contact_id}/delete",
        data={"csrf_token": login.csrf_token},
    )
    assert denied.status_code == 404
    removed = client.post(
        f"/profile/contacts/{own_contact_id}/delete",
        data={"csrf_token": login.csrf_token},
        follow_redirects=False,
    )
    assert removed.status_code == 303
    activity = client.get("/activity")
    assert "Profile Changed" in activity.text
    assert "Preferences Changed" in activity.text


def test_sessions_revoke_other_and_logout(client, login_user) -> None:
    current = login_user(subject="session-route-user")
    other = login_user(subject="session-route-user", oidc_sid="sid-other")
    client.cookies.set(client.app.state.settings.SESSION_COOKIE_NAME, current.raw_session_id)
    response = client.post(
        f"/sessions/{other.session_id}/revoke",
        data={"csrf_token": current.csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    current_revoke = client.post(
        f"/sessions/{current.session_id}/revoke",
        data={"csrf_token": current.csrf_token},
    )
    assert current_revoke.status_code == 400
    logout = client.post("/logout", data={"csrf_token": current.csrf_token}, follow_redirects=False)
    assert logout.status_code == 303
    assert urlparse(logout.headers["location"]).netloc == "auth.test"


def test_connected_service_internal_touch_is_read_only(client, login_user) -> None:
    login = login_user(subject="service-user")

    async def seed_service() -> None:
        async with client.app.state.database.session_factory() as db:
            db.add(
                ServiceRegistry(
                    service_key="ygit-net",
                    display_name="YGit",
                    domain="ygit.net",
                    description="Git hosting",
                    active=True,
                    sort_order=1,
                )
            )
            await db.commit()

    asyncio.run(seed_service())
    unauthorized = client.post(
        "/internal/v1/service-connections/touch",
        json={
            "subject": login.subject,
            "service_key": "ygit-net",
            "authenticated_at": datetime.now(UTC).isoformat(),
        },
    )
    assert unauthorized.status_code == 401
    client.app.state.validator.service_claims["azp"] = "vib-tools-backend"
    cross_service = client.post(
        "/internal/v1/service-connections/touch",
        headers={"Authorization": "Bearer valid-service-token"},
        json={
            "subject": login.subject,
            "service_key": "ygit-net",
            "authenticated_at": datetime.now(UTC).isoformat(),
        },
    )
    assert cross_service.status_code == 403
    client.app.state.validator.service_claims["azp"] = "ygit-net-backend"
    touched = client.post(
        "/internal/v1/service-connections/touch",
        headers={"Authorization": "Bearer valid-service-token"},
        json={
            "subject": login.subject,
            "service_key": "ygit-net",
            "authenticated_at": datetime.now(UTC).isoformat(),
        },
    )
    assert touched.status_code == 204
    page = client.get("/services")
    assert "YGit" in page.text
    assert "ygit.net" in page.text
    assert not re.search(r"client[_ -]?id|access[_ -]?token", page.text, re.I)


def test_health_body_limit_validation_and_not_found(client) -> None:
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    client.app.state.validator = type(
        "ReadyValidator",
        (),
        {"metadata": lambda self: asyncio.sleep(0, result=object())},
    )()
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    oversized = client.post(
        "/auth/backchannel-logout",
        content=b"x" * (70 * 1024),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert oversized.status_code == 413
    not_found = client.get("/does-not-exist")
    assert not_found.status_code == 404
    assert "request" in not_found.text.lower() or "not found" in not_found.text.lower()


def test_quick_theme_updates_only_theme_and_rejects_external_next(client, login_user) -> None:
    login = login_user(subject="quick-theme-user")

    updated = client.post(
        "/preferences/quick-theme",
        data={
            "csrf_token": login.csrf_token,
            "theme": "dark",
            "next": "/security",
        },
        follow_redirects=False,
    )
    assert updated.status_code == 303
    assert updated.headers["location"] == "/security"
    security = client.get("/security")
    assert 'data-theme="dark"' in security.text

    invalid = client.post(
        "/preferences/quick-theme",
        data={
            "csrf_token": login.csrf_token,
            "theme": "not-a-theme",
            "next": "https://evil.example/",
        },
        follow_redirects=False,
    )
    assert invalid.status_code == 303
    assert invalid.headers["location"] == "/"
    overview = client.get("/")
    assert 'data-theme="dark"' in overview.text


def test_preferences_invalid_locale_renders_validation_error(client, login_user) -> None:
    login = login_user(subject="invalid-locale-user")
    response = client.post(
        "/preferences",
        data={
            "csrf_token": login.csrf_token,
            "theme": "system",
            "locale": "",
            "timezone": "UTC",
        },
    )
    assert response.status_code == 422
    assert "Language setting is invalid" in response.text
    saved_page = client.get("/preferences?saved=1")
    assert saved_page.status_code == 200
    assert "Your changes were saved securely" in saved_page.text


def test_brand_assets_and_command_palette_contract(client, login_user) -> None:
    login_user(subject="brand-contract-user")

    for asset in (
        "/static/brand/vibtools-horizontal-dark.png",
        "/static/brand/vibtools-horizontal-light.png",
        "/static/brand/vibtools-icon-dark.png",
        "/static/brand/vibtools-icon-light.png",
        "/static/brand/vibtools-favicon.png",
    ):
        response = client.get(asset)
        assert response.status_code == 200, asset
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 100

    page = client.get("/")
    assert page.status_code == 200
    assert "data-command-palette" in page.text
    assert "data-command-input" in page.text
    assert "data-command-item" in page.text
    assert "Ctrl" in page.text
