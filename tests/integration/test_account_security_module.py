from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.auth.keycloak_management import (
    CentralAccountStatus,
    KeycloakManagementClient,
    KeycloakUnavailable,
)
from app.database.models.security import SecurityActivity
from app.database.models.service import ServiceRegistry
from app.services_registry.repository import touch_connection


class FullFakeKeycloak:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.required_actions: list[tuple[str, list[str], str | None]] = []
        self.verify_email_calls: list[tuple[str, str | None]] = []
        self.email_updates: list[tuple[str, str, str | None]] = []
        self.removed_totp: list[str] = []
        self.revoked_consents: list[tuple[str, str]] = []

    async def account_status(self, subject: str) -> CentralAccountStatus:
        del subject
        if self.fail:
            return CentralAccountStatus(None, None, None, None, False)
        return CentralAccountStatus(True, True, True, 2, True)

    async def execute_required_actions_email(
        self, subject: str, *, actions: list[str], redirect_uri: str | None = None
    ) -> None:
        if self.fail:
            raise KeycloakUnavailable("down")
        self.required_actions.append((subject, actions, redirect_uri))

    async def send_verify_email(self, subject: str, *, redirect_uri: str | None = None) -> None:
        if self.fail:
            raise KeycloakUnavailable("down")
        self.verify_email_calls.append((subject, redirect_uri))

    async def update_user_email(
        self, subject: str, email: str, *, redirect_uri: str | None = None
    ) -> None:
        if self.fail:
            raise KeycloakUnavailable("down")
        self.email_updates.append((subject, email, redirect_uri))

    async def remove_totp_credentials(self, subject: str) -> bool:
        if self.fail:
            raise KeycloakUnavailable("down")
        self.removed_totp.append(subject)
        return True

    async def list_user_sessions(self, subject: str) -> list[dict[str, Any]]:
        del subject
        if self.fail:
            raise KeycloakUnavailable("down")
        return [
            {
                "id": "central-1",
                "username": "raj",
                "ipAddress": "203.0.113.10",
                "clients": {"vib-id-portal": "Vib ID"},
                "start": 1,
                "lastAccess": 2,
            }
        ]

    async def revoke_user_consent(self, subject: str, client_id: str) -> bool:
        if self.fail:
            raise KeycloakUnavailable("down")
        self.revoked_consents.append((subject, client_id))
        return True


def test_native_security_pages_actions_and_apis(client, login_user) -> None:
    login = login_user(subject="security-module-user")
    fake = FullFakeKeycloak()
    client.app.state.keycloak = fake

    async def seed_service() -> None:
        async with client.app.state.database.session_factory() as db:
            db.add(
                ServiceRegistry(
                    service_key="ygit-net",
                    display_name="YGit",
                    domain="ygit.net",
                    description="Open-source web platform",
                    active=True,
                    sort_order=1,
                )
            )
            await db.flush()
            await touch_connection(
                db,
                subject=login.subject,
                service_key="ygit-net",
                authenticated_at=datetime.now(UTC),
            )
            await db.commit()

    asyncio.run(seed_service())

    for path, expected in (
        ("/security", "Native Security Module"),
        ("/security/password", "Password security"),
        ("/security/email", "Email security"),
        ("/security/2fa", "Two-factor authentication"),
        ("/security/recovery-codes", "Recovery codes"),
        ("/security/sessions", "Security sessions"),
        ("/applications", "YGit"),
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert expected in response.text
        assert "server-only-access-token" not in response.text
        assert "auth.test/realms/vib/account" not in response.text

    api_profile = client.get("/api/account/profile")
    assert api_profile.status_code == 200
    assert api_profile.json()["subject"] == login.subject
    assert client.get("/api/security/status").json()["central_available"] is True
    assert client.get("/api/security/2fa/status").json()["enabled"] is True
    assert client.get("/api/security/sessions").json()["central"][0]["id"] == "central-1"
    assert client.get("/api/applications").json()["applications"][0]["service_key"] == "ygit-net"

    assert (
        client.post(
            "/security/password/change-request",
            data={"csrf_token": login.csrf_token},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert fake.required_actions[-1][1] == ["UPDATE_PASSWORD"]

    assert (
        client.post(
            "/security/email/resend-verification",
            data={"csrf_token": login.csrf_token},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert fake.verify_email_calls

    assert (
        client.post(
            "/security/email/change-request",
            data={"csrf_token": login.csrf_token, "new_email": "new@example.com"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert fake.email_updates[-1][1] == "new@example.com"

    invalid_email = client.post(
        "/security/email/change-request",
        data={"csrf_token": login.csrf_token, "new_email": "not-valid"},
    )
    assert invalid_email.status_code == 422
    assert "Enter a valid email address" in invalid_email.text

    assert (
        client.post(
            "/security/2fa/enable",
            data={"csrf_token": login.csrf_token},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert fake.required_actions[-1][1] == ["CONFIGURE_TOTP"]

    assert (
        client.post(
            "/security/2fa/disable",
            data={"csrf_token": login.csrf_token},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert fake.removed_totp == [login.subject]

    consent_missing_csrf = client.delete("/api/applications/ygit/consent")
    assert consent_missing_csrf.status_code == 403
    consent = client.delete(
        "/api/applications/ygit/consent",
        headers={"x-csrf-token": login.csrf_token},
    )
    assert consent.status_code == 200
    assert consent.json()["revoked"] is True

    async def audit_events() -> list[str]:
        async with client.app.state.database.session_factory() as db:
            return [
                item.event_type
                for item in (await db.execute(select(SecurityActivity))).scalars().all()
            ]

    events = asyncio.run(audit_events())
    assert "password_change_requested" in events
    assert "email_change_requested" in events
    assert "mfa_enable_requested" in events
    assert "mfa_disable_requested" in events
    assert "application_consent_revoked" in events


def test_security_module_failure_and_session_routes(client, login_user) -> None:
    current = login_user(subject="security-session-user")
    other = login_user(subject="security-session-user", oidc_sid="sid-other")
    client.cookies.set(client.app.state.settings.SESSION_COOKIE_NAME, current.raw_session_id)
    client.app.state.keycloak = FullFakeKeycloak(fail=True)

    unavailable = client.get("/security/sessions")
    assert unavailable.status_code == 200
    assert "unavailable" in unavailable.text.lower()

    failed_password = client.post(
        "/security/password/change-request",
        data={"csrf_token": current.csrf_token},
        follow_redirects=False,
    )
    assert failed_password.status_code == 303
    assert failed_password.headers["location"].endswith("central_unavailable")

    revoked = client.post(
        f"/security/sessions/{other.session_id}/revoke",
        data={"csrf_token": current.csrf_token},
        follow_redirects=False,
    )
    assert revoked.status_code == 303
    self_revoke = client.post(
        f"/security/sessions/{current.session_id}/revoke",
        data={"csrf_token": current.csrf_token},
    )
    assert self_revoke.status_code == 400
    all_other = client.post(
        "/security/sessions/logout-all",
        data={"csrf_token": current.csrf_token},
        follow_redirects=False,
    )
    assert all_other.status_code == 303


class RecordingKeycloak(KeycloakManagementClient):
    def __init__(self) -> None:
        self.settings = type(
            "Settings",
            (),
            {
                "OIDC_ISSUER_URL": "https://auth.vib.tools/realms/vib",
                "OIDC_CLIENT_ID": "vib-id-portal",
            },
        )()
        self.calls: list[tuple[str, str, object | None]] = []
        self.user_payload: dict[str, Any] = {
            "id": "user-1",
            "username": "raj",
            "email": "old@example.test",
            "enabled": True,
            "attributes": {"tier": ["standard"]},
        }

    async def _request(self, method: str, path: str, *, json: object | None = None) -> Any:
        self.calls.append((method, path, json))
        if path.endswith("/credentials"):
            return [{"id": "cred-1", "type": "otp"}, {"id": "cred-2", "type": "password"}]
        if path.endswith("/sessions"):
            return [{"id": "central-1"}]
        if path.endswith("/consents"):
            return [{"clientId": "ygit"}]
        if path.endswith("/users/user-1") and method == "GET":
            return self.user_payload
        return None


def test_keycloak_management_extended_methods() -> None:
    kc = RecordingKeycloak()

    async def exercise() -> None:
        assert await kc.get_user("user-1") == kc.user_payload
        await kc.send_verify_email("user-1", redirect_uri="https://id.vib.tools/security/email")
        await kc.execute_required_actions_email(
            "user-1", actions=["UPDATE_PASSWORD", "UNSAFE"], redirect_uri="https://id.vib.tools/"
        )
        await kc.update_user_email("user-1", "new@example.com")
        assert await kc.list_user_sessions("user-1") == [{"id": "central-1"}]
        assert await kc.list_user_credentials("user-1")
        assert await kc.remove_totp_credentials("user-1") is True
        assert await kc.list_user_consents("user-1") == [{"clientId": "ygit"}]
        assert await kc.revoke_user_consent("user-1", "ygit") is True
        assert await kc.revoke_user_consent("user-1", "missing") is False

    asyncio.run(exercise())
    paths = [call[1] for call in kc.calls]
    assert any("execute-actions-email" in path for path in paths)
    assert any("send-verify-email" in path for path in paths)
    assert any("credentials/cred-1" in path for path in paths)
    update_calls = [call for call in kc.calls if call[0] == "PUT" and call[1] == "/users/user-1"]
    assert update_calls
    assert isinstance(update_calls[0][2], dict)
    assert update_calls[0][2]["emailVerified"] is False


def test_account_security_service_defensive_branches() -> None:
    from app.account_security.service import central_session_summaries, safe_central_sessions

    assert central_session_summaries(
        [
            {"id": "dict-clients", "clients": {"a": "App A"}},
            {"id": "list-clients", "clients": ["App B", None]},
            {"id": ""},
        ]
    )[1].clients == ["App B"]

    class NoSessions:
        pass

    class BadSessions:
        async def list_user_sessions(self, subject: str) -> object:
            del subject
            return {"not": "a-list"}

    async def exercise() -> None:
        assert await safe_central_sessions(NoSessions(), "user") == []
        assert await safe_central_sessions(BadSessions(), "user") == []

    asyncio.run(exercise())
