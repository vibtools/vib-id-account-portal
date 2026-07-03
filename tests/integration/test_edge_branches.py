from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.accounts.repository import (
    add_contact,
    delete_contact,
    ensure_account_records,
    get_preferences,
    list_contacts,
    update_preferences,
    update_profile,
)
from app.accounts.schemas import ContactCreate, ProfileUpdate
from app.auth.keycloak_management import KeycloakUnavailable
from app.auth.oidc import OIDCFlowError
from app.database.models.enums import ContactType, Theme
from app.database.models.service import ServiceRegistry
from app.services_registry.repository import (
    list_services,
    list_user_connections,
    touch_connection,
    upsert_service,
)


def test_repository_edge_cases_and_service_upsert(client) -> None:
    async def exercise() -> None:
        async with client.app.state.database.session_factory() as db:
            profile, _ = await ensure_account_records(
                db, subject="edge-user", display_name="", locale="en"
            )
            assert profile.display_name == "Vib ID user"
            await ensure_account_records(db, subject="edge-user", display_name="Ignored")
            with pytest.raises(LookupError):
                await update_profile(
                    db,
                    subject="missing-user",
                    payload=ProfileUpdate(
                        display_name="Missing",
                        timezone="UTC",
                        preferred_language="en",
                        version=datetime.now(UTC),
                    ),
                )
            first = await add_contact(
                db,
                subject="edge-user",
                payload=ContactCreate(
                    contact_type=ContactType.EMAIL,
                    label="One",
                    value="one@example.com",
                    is_primary=True,
                ),
                contact_limit=2,
            )
            second = await add_contact(
                db,
                subject="edge-user",
                payload=ContactCreate(
                    contact_type=ContactType.EMAIL,
                    label="Two",
                    value="two@example.com",
                    is_primary=True,
                ),
                contact_limit=2,
            )
            assert not first.is_primary and second.is_primary
            with pytest.raises(ValueError):
                await add_contact(
                    db,
                    subject="edge-user",
                    payload=ContactCreate(
                        contact_type=ContactType.OTHER, label="Third", value="third"
                    ),
                    contact_limit=2,
                )
            assert len(await list_contacts(db, "edge-user")) == 2
            assert await delete_contact(db, subject="edge-user", contact_id=first.id)
            assert not await delete_contact(db, subject="edge-user", contact_id=first.id)

            missing_pref = await update_preferences(
                db,
                subject="new-pref-user",
                theme=Theme.LIGHT,
                locale="en",
                timezone_name="UTC",
                security_notifications=False,
            )
            assert missing_pref.theme == Theme.LIGHT
            assert await get_preferences(db, "new-pref-user") is not None

            service = await upsert_service(
                db,
                service_key="edge-service",
                display_name="Edge Service",
                domain="EDGE.EXAMPLE",
                description="Testing",
                icon_reference=None,
                active=True,
                sort_order=2,
            )
            assert service.domain == "edge.example"
            same = await upsert_service(
                db,
                service_key="edge-service",
                display_name="Edge Service 2",
                domain="edge.example",
                description="Updated",
                icon_reference="icons/edge.svg",
                active=True,
                sort_order=1,
            )
            assert same.id == service.id
            created, is_new = await touch_connection(
                db,
                subject="edge-user",
                service_key="edge-service",
                authenticated_at=datetime.now(UTC) - timedelta(minutes=1),
            )
            assert is_new
            touched, is_new = await touch_connection(
                db,
                subject="edge-user",
                service_key="edge-service",
                authenticated_at=datetime.now(UTC),
            )
            assert not is_new and touched.id == created.id
            assert len(await list_user_connections(db, "edge-user")) == 1
            assert len(await list_services(db)) == 1
            with pytest.raises(LookupError):
                await touch_connection(
                    db,
                    subject="edge-user",
                    service_key="missing-service",
                    authenticated_at=datetime.now(UTC),
                )
            await db.commit()

    asyncio.run(exercise())


def test_invalid_form_branches_activity_bounds_and_session_actions(client, login_user) -> None:
    current = login_user(subject="branch-user")
    other = login_user(subject="branch-user", oidc_sid="other-sid")
    client.cookies.set(client.app.state.settings.SESSION_COOKIE_NAME, current.raw_session_id)

    bad_profile = client.post(
        "/profile",
        data={
            "csrf_token": current.csrf_token,
            "display_name": "",
            "timezone": "Invalid/Timezone",
            "preferred_language": "bad code",
            "version": "not-a-date",
        },
    )
    assert bad_profile.status_code == 422
    bad_contact = client.post(
        "/profile/contacts",
        data={
            "csrf_token": current.csrf_token,
            "contact_type": "email",
            "label": "Bad",
            "value": "not-an-email",
        },
    )
    assert bad_contact.status_code == 422
    bad_preferences = client.post(
        "/preferences",
        data={
            "csrf_token": current.csrf_token,
            "theme": "impossible",
            "locale": "",
            "timezone": "No/Such",
        },
    )
    assert bad_preferences.status_code == 422
    assert client.get("/activity?page=100").status_code == 200
    assert client.get("/activity?days=999").status_code == 422

    revoke_all = client.post(
        "/sessions/revoke-all-others",
        data={"csrf_token": current.csrf_token},
        follow_redirects=False,
    )
    assert revoke_all.status_code == 303

    everywhere = client.post(
        "/sessions/sign-out-everywhere",
        data={"csrf_token": current.csrf_token},
        follow_redirects=False,
    )
    assert everywhere.status_code == 303
    assert current.subject in client.app.state.keycloak.logout_calls

    class DownKeycloak:
        async def logout_user(self, subject: str) -> None:
            del subject
            raise KeycloakUnavailable("down")

        async def account_status(self, subject: str):
            del subject
            return None

    # Re-authenticate after sign-out-everywhere revoked the first session.
    current = login_user(subject="branch-user-2")
    client.app.state.keycloak = DownKeycloak()
    down = client.post(
        "/sessions/sign-out-everywhere",
        data={"csrf_token": current.csrf_token},
    )
    assert down.status_code == 503
    del other


def test_auth_failure_refresh_and_health_unavailable_branches(client, login_user) -> None:
    class FailingOIDC:
        async def complete_login(self, db, *, state: str, code: str):
            del db, state, code
            raise OIDCFlowError("rejected")

    client.app.state.oidc = FailingOIDC()
    callback = client.get("/auth/callback?state=s&code=c", follow_redirects=False)
    assert callback.status_code == 303
    assert callback.headers["location"] == "/auth/error"
    assert client.post("/auth/backchannel-logout", data={"logout_token": "bad"}).status_code == 400

    class DownValidator:
        async def metadata(self):
            raise RuntimeError("down")

    client.app.state.validator = DownValidator()
    ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.json()["oidc"] == "unavailable"

    login = login_user(subject="logout-local")

    class NoEndSessionValidator:
        async def metadata(self):
            from app.auth.token_validation import OIDCMetadata

            return OIDCMetadata("i", "a", "t", "j", None)

    client.app.state.validator = NoEndSessionValidator()
    logout = client.post("/logout", data={"csrf_token": login.csrf_token}, follow_redirects=False)
    assert logout.status_code == 303
    assert logout.headers["location"] == client.app.state.settings.OIDC_POST_LOGOUT_REDIRECT_URI


def test_inactive_service_is_not_visible(client, login_user) -> None:
    login_user(subject="inactive-user")

    async def seed() -> None:
        async with client.app.state.database.session_factory() as db:
            db.add(
                ServiceRegistry(
                    service_key="inactive",
                    display_name="Inactive",
                    domain="inactive.example",
                    description="Hidden",
                    active=False,
                    sort_order=1,
                )
            )
            await db.commit()

    asyncio.run(seed())
    response = client.post(
        "/internal/v1/service-connections/touch",
        headers={"Authorization": "Bearer valid-service-token"},
        json={
            "subject": "inactive-user",
            "service_key": "inactive",
            "authenticated_at": datetime.now(UTC).isoformat(),
        },
    )
    assert response.status_code == 403


def test_activity_repository_accepts_upper_date_bound(client, login_user) -> None:
    from datetime import UTC, datetime, timedelta

    from app.activity.repository import list_activity

    login = login_user(subject="activity-bound-user")

    async def exercise() -> None:
        async with client.app.state.database.session_factory() as db:
            records, total = await list_activity(
                db,
                subject=login.subject,
                page=1,
                date_to=datetime.now(UTC) + timedelta(minutes=1),
            )
            assert isinstance(records, list)
            assert total >= 0

    asyncio.run(exercise())
