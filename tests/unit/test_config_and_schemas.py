from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.accounts.schemas import ContactCreate, ProfileUpdate, ServiceTouchPayload, clean_text
from app.config import Settings
from app.database.models.enums import ContactType

BASE = {
    "APP_ENV": "test",
    "APP_BASE_URL": "http://testserver",
    "APP_SECRET_KEY": "a" * 32,
    "TOKEN_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "OIDC_ISSUER_URL": "http://auth.test/realms/vib",
    "OIDC_CLIENT_SECRET": "b" * 32,
    "OIDC_REDIRECT_URI": "http://testserver/auth/callback",
    "OIDC_POST_LOGOUT_REDIRECT_URI": "http://testserver/",
    "KEYCLOAK_MANAGEMENT_CLIENT_SECRET": "c" * 32,
    "KEYCLOAK_ACCOUNT_URL": "http://auth.test/realms/vib/account/",
    "CSRF_SECRET": "d" * 32,
    "IP_PRIVACY_KEY": "e" * 32,
    "TRUSTED_HOSTS": "testserver",
    "SESSION_COOKIE_SECURE": False,
}


def test_settings_accept_secure_test_and_parse_allowlists() -> None:
    settings = Settings(**BASE, KEYCLOAK_ALLOWED_INTERNAL_CLIENTS="a,b, a")
    assert settings.trusted_hosts == ["testserver"]
    assert settings.allowed_internal_clients == {"a", "b"}


def test_settings_fail_closed_for_insecure_production() -> None:
    with pytest.raises(ValidationError):
        Settings(**{**BASE, "APP_ENV": "production"})
    with pytest.raises(ValidationError):
        Settings(**{**BASE, "APP_SECRET_KEY": "short"})
    with pytest.raises(ValidationError):
        Settings(**{**BASE, "TRUSTED_HOSTS": "*"})
    with pytest.raises(ValidationError):
        Settings(**{**BASE, "OIDC_REDIRECT_URI": "http://other/callback"})
    with pytest.raises(ValidationError):
        Settings(**{**BASE, "OIDC_SCOPES": "openid email"})


def test_profile_validation_normalizes_phone_and_unicode() -> None:
    profile = ProfileUpdate(
        display_name="  Ráj  ",
        phone_number="1712345678",
        phone_country_code="+880",
        country_code="bd",
        timezone="Asia/Dhaka",
        preferred_language="bn-BD",
        organization_name=" Vib Tools ",
        job_title="Developer",
        version=datetime.now(UTC),
    )
    assert profile.display_name == "Ráj"
    assert profile.phone_number == "+8801712345678"
    assert profile.phone_country_code == "+880"
    assert profile.country_code == "BD"
    with pytest.raises(ValidationError):
        ProfileUpdate(
            display_name="Bad\x00Name",
            timezone="Invalid/Zone",
            preferred_language="bad code",
            version=datetime.now(UTC),
        )
    with pytest.raises(ValueError):
        clean_text("", max_length=4, required=True)


def test_contact_and_service_payload_validation() -> None:
    email = ContactCreate(contact_type=ContactType.EMAIL, label="Work", value="A@Example.COM")
    assert email.normalized() == "a@example.com"
    phone = ContactCreate(contact_type=ContactType.PHONE, label="Mobile", value="+8801712345678")
    assert phone.normalized() == "+8801712345678"
    with pytest.raises(ValueError):
        ContactCreate(contact_type=ContactType.EMAIL, label="Bad", value="invalid").normalized()
    with pytest.raises(ValueError):
        ContactCreate(
            contact_type=ContactType.EMAIL,
            label="Bad",
            value="a@b..example",
        ).normalized()
    payload = ServiceTouchPayload(
        subject="central-subject",
        service_key="ygit-net",
        authenticated_at=datetime.now(UTC),
    )
    assert payload.service_key == "ygit-net"
    with pytest.raises(ValidationError):
        ServiceTouchPayload(
            subject="ok-subject",
            service_key="BAD_KEY",
            authenticated_at=datetime.now(UTC).replace(tzinfo=None),
        )
    with pytest.raises(ValidationError):
        ServiceTouchPayload(
            subject="ok-subject",
            service_key="ygit-net",
            authenticated_at=datetime.now(UTC) + timedelta(minutes=6),
        )
