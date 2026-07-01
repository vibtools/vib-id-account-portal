from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

TEST_DB = Path("/tmp/vib-id-account-portal-pytest.db")

_ENV = {
    "APP_ENV": "test",
    "APP_NAME": "Vib ID",
    "APP_BASE_URL": "http://testserver",
    "APP_SECRET_KEY": "a" * 32,
    "TOKEN_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", f"sqlite+aiosqlite:///{TEST_DB}"),
    "OIDC_ISSUER_URL": "http://auth.test/realms/vib",
    "OIDC_CLIENT_ID": "vib-id-portal",
    "OIDC_CLIENT_SECRET": "b" * 32,
    "OIDC_REDIRECT_URI": "http://testserver/auth/callback",
    "OIDC_POST_LOGOUT_REDIRECT_URI": "http://testserver/",
    "OIDC_SCOPES": "openid profile email",
    "OIDC_EXPECTED_AUDIENCE": "vib-id-portal",
    "KEYCLOAK_MANAGEMENT_CLIENT_ID": "vib-id-portal-management",
    "KEYCLOAK_MANAGEMENT_CLIENT_SECRET": "c" * 32,
    "KEYCLOAK_MANAGEMENT_AUDIENCE": "account",
    "KEYCLOAK_ACCOUNT_URL": "http://auth.test/realms/vib/account/",
    "KEYCLOAK_ALLOWED_INTERNAL_CLIENTS": "ygit-backend,vib-tools-backend",
    "SESSION_COOKIE_NAME": "vib_id_test_session",
    "SESSION_COOKIE_SECURE": "false",
    "TRUSTED_HOSTS": "testserver,localhost,127.0.0.1",
    "CSRF_SECRET": "d" * 32,
    "IP_PRIVACY_KEY": "e" * 32,
    "RATE_LIMIT_ENABLED": "true",
    "LOG_LEVEL": "WARNING",
}
for key, value in _ENV.items():
    os.environ[key] = value

from app.accounts.repository import ensure_account_records  # noqa: E402
from app.auth.keycloak_management import CentralAccountStatus  # noqa: E402
from app.auth.token_validation import OIDCMetadata  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.session import Database  # noqa: E402
from app.main import create_app  # noqa: E402


class FakeKeycloak:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.logout_calls: list[str] = []

    async def account_status(self, subject: str) -> CentralAccountStatus:
        del subject
        return CentralAccountStatus(
            enabled=True if self.available else None,
            email_verified=True if self.available else None,
            two_factor_enabled=True if self.available else None,
            session_count=2 if self.available else None,
            available=self.available,
        )

    async def logout_user(self, subject: str) -> None:
        self.logout_calls.append(subject)


class FakeValidator:
    def __init__(self) -> None:
        self.service_claims: dict[str, Any] = {
            "sub": "9a21b70d-632e-4a92-b9ca-e0e54b6cf378",
            "azp": "ygit-backend",
            "preferred_username": "service-account-ygit-backend",
        }
        self.logout_claims: dict[str, Any] = {
            "jti": "logout-jti",
            "sid": "central-session-1",
            "exp": 4_102_444_800,
        }

    async def metadata(self, *, force: bool = False) -> OIDCMetadata:
        del force
        return OIDCMetadata(
            issuer="http://auth.test/realms/vib",
            authorization_endpoint="http://auth.test/authorize",
            token_endpoint="http://auth.test/token",
            jwks_uri="http://auth.test/jwks",
            end_session_endpoint="http://auth.test/logout",
        )

    async def validate_service_token(self, token: str) -> dict[str, Any]:
        if token != "valid-service-token":
            from app.auth.token_validation import TokenValidationError

            raise TokenValidationError("invalid service token")
        return self.service_claims

    async def validate_logout_token(self, token: str) -> dict[str, Any]:
        if token != "valid-logout-token":
            from app.auth.token_validation import TokenValidationError

            raise TokenValidationError("invalid logout token")
        return self.logout_claims


async def _recreate_schema() -> None:
    get_settings.cache_clear()
    database = Database(get_settings())
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    await database.dispose()


@pytest.fixture(autouse=True)
def clean_database() -> None:
    asyncio.run(_recreate_schema())


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    application = create_app()
    with TestClient(application, base_url="http://testserver") as test_client:
        test_client.app.state.keycloak = FakeKeycloak()
        test_client.app.state.validator = FakeValidator()
        yield test_client


@dataclass(slots=True)
class LoginResult:
    subject: str
    raw_session_id: str
    session_id: Any
    csrf_token: str


@pytest.fixture
def login_user(client: TestClient) -> Callable[..., LoginResult]:
    def login(
        *,
        subject: str = "user-123",
        display_name: str = "Raj Test",
        email_verified: bool = True,
        oidc_sid: str = "central-session-1",
    ) -> LoginResult:
        async def seed() -> LoginResult:
            async with client.app.state.database.session_factory() as db:
                await ensure_account_records(
                    db,
                    subject=subject,
                    display_name=display_name,
                    locale="en",
                )
                auth = await client.app.state.session_service.create(
                    db,
                    subject=subject,
                    token_bundle={
                        "access_token": "server-only-access-token",
                        "refresh_token": "server-only-refresh-token",
                        "id_token": "server-only-id-token",
                        "_id_claims": {
                            "sub": subject,
                            "name": display_name,
                            "email": "raj@example.test",
                            "email_verified": email_verified,
                        },
                    },
                    user_agent="Mozilla/5.0 Chrome/149.0 Windows NT 10.0",
                    ip_address="203.0.113.10",
                    oidc_sid=oidc_sid,
                )
                await db.commit()
                return LoginResult(
                    subject=subject,
                    raw_session_id=auth.raw_id,
                    session_id=auth.model.id,
                    csrf_token=client.app.state.csrf.token_for_session(auth.raw_id),
                )

        result = asyncio.run(seed())
        client.cookies.set(client.app.state.settings.SESSION_COOKIE_NAME, result.raw_session_id)
        return result

    return login


@pytest.fixture(scope="session")
def live_server_url() -> str:
    import socket
    import threading
    import time

    import uvicorn

    get_settings.cache_clear()
    application = create_app()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = uvicorn.Config(
        application,
        host="127.0.0.1",
        port=port,
        log_level="critical",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("test server did not start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
