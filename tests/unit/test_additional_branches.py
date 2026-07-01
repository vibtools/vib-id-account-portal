from __future__ import annotations

import asyncio

import httpx
import pytest
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.auth.oidc import OIDCClient, OIDCFlowError
from app.auth.token_validation import OIDCMetadata
from app.config import Settings, get_settings
from app.database.session import Database
from app.middleware.body_limit import RequestBodyLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.security.encryption import EncryptionError, TokenCipher
from app.security.identifiers import device_label, sanitize_user_agent
from app.services_registry.service import validate_service_metadata

PRODUCTION = {
    "APP_ENV": "production",
    "APP_BASE_URL": "https://id.vib.tools",
    "APP_SECRET_KEY": "a" * 32,
    "TOKEN_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "DATABASE_URL": "postgresql+asyncpg://user:pass@db:5432/vibid",
    "OIDC_ISSUER_URL": "https://auth.vib.tools/realms/vib",
    "OIDC_CLIENT_SECRET": "b" * 32,
    "OIDC_REDIRECT_URI": "https://id.vib.tools/auth/callback",
    "OIDC_POST_LOGOUT_REDIRECT_URI": "https://id.vib.tools/",
    "KEYCLOAK_MANAGEMENT_CLIENT_SECRET": "c" * 32,
    "KEYCLOAK_ACCOUNT_URL": "https://auth.vib.tools/realms/vib/account/",
    "SESSION_COOKIE_SECURE": True,
    "CSRF_SECRET": "d" * 32,
    "IP_PRIVACY_KEY": "e" * 32,
    "TRUSTED_HOSTS": "id.vib.tools",
}


def test_production_config_accepts_locked_hosts_and_rejects_each_unsafe_axis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    assert Settings(_env_file=None, **PRODUCTION).APP_ENV == "production"
    bad_cases = (
        {
            "APP_BASE_URL": "http://id.vib.tools",
            "OIDC_REDIRECT_URI": "http://id.vib.tools/auth/callback",
        },
        {"SESSION_COOKIE_SECURE": False},
        {"DATABASE_URL": "sqlite+aiosqlite:///bad.db"},
        {
            "OIDC_ISSUER_URL": "https://evil.test/realms/vib",
            "KEYCLOAK_ACCOUNT_URL": "https://evil.test/realms/vib/account/",
        },
        {
            "APP_BASE_URL": "https://other.test",
            "OIDC_REDIRECT_URI": "https://other.test/auth/callback",
            "OIDC_POST_LOGOUT_REDIRECT_URI": "https://other.test/",
        },
        {"OIDC_POST_LOGOUT_REDIRECT_URI": "https://other.test/"},
        {"KEYCLOAK_ACCOUNT_URL": "https://other.test/account/"},
        {"TOKEN_ENCRYPTION_KEY": "not-fernet"},
        {"DATABASE_URL": "mysql://db"},
    )
    for overrides in bad_cases:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{**PRODUCTION, **overrides})


def test_remaining_identifier_and_service_validation_branches() -> None:
    assert sanitize_user_agent(None) == "Unknown client"
    assert device_label("Edg/1 Macintosh") == "Microsoft Edge on macOS"
    assert device_label("Safari/1 iPhone") == "Safari on iOS/iPadOS"
    assert device_label("unknown") == "Browser on Unknown device"
    common = {
        "service_key": "valid-key",
        "domain": "example.com",
        "display_name": "Name",
        "description": "description",
        "icon_reference": None,
        "sort_order": 1,
    }
    invalid = (
        {**common, "domain": "bad"},
        {**common, "display_name": ""},
        {**common, "description": ""},
        {**common, "sort_order": 100001},
        {**common, "icon_reference": "https://evil/icon.svg"},
    )
    for case in invalid:
        with pytest.raises(ValueError):
            validate_service_metadata(**case)


def test_encryption_invalid_utf8_and_database_context_rollback() -> None:
    cipher = TokenCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    with pytest.raises(EncryptionError):
        cipher.decrypt_json(cipher.encrypt_bytes(b"\xff"))

    async def exercise() -> None:
        database = Database(get_settings())
        with pytest.raises(RuntimeError):
            async with database.session() as session:
                assert session.is_active
                raise RuntimeError("rollback")
        await database.dispose()

    asyncio.run(exercise())


def test_request_body_middleware_non_http_invalid_length_and_chunk_limit() -> None:
    async def non_http_app(scope, receive, send):
        del receive, send
        assert scope["type"] == "websocket"

    async def websocket_receive():
        return {"type": "websocket.disconnect"}

    async def websocket_send(message):
        del message

    asyncio.run(
        RequestBodyLimitMiddleware(non_http_app)(
            {"type": "websocket"}, websocket_receive, websocket_send
        )
    )

    async def downstream(scope, receive, send):
        del scope
        while True:
            message = await receive()
            if message["type"] == "http.request" and not message.get("more_body", False):
                break
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def invoke(scope, messages):
        sent = []
        iterator = iter(messages)

        async def receive():
            return next(iterator)

        async def send(message):
            sent.append(message)

        await RequestBodyLimitMiddleware(downstream, max_bytes=4)(scope, receive, send)
        return sent

    base_scope = {"type": "http", "headers": []}
    invalid = asyncio.run(invoke({**base_scope, "headers": [(b"content-length", b"bad")]}, []))
    assert invalid[0]["status"] == 413
    declared_large = asyncio.run(invoke({**base_scope, "headers": [(b"content-length", b"5")]}, []))
    assert declared_large[0]["status"] == 413
    too_large = asyncio.run(
        invoke(base_scope, [{"type": "http.request", "body": b"12345", "more_body": False}])
    )
    assert too_large[0]["status"] == 413
    okay = asyncio.run(
        invoke(
            base_scope,
            [
                {"type": "http.request", "body": b"12", "more_body": True},
                {"type": "http.request", "body": b"34", "more_body": False},
            ],
        )
    )
    assert okay[0]["status"] == 204


def test_security_headers_production_paths() -> None:
    async def app(scope, receive, send):
        del scope, receive, send

    async def exercise(path: str):
        middleware = SecurityHeadersMiddleware(app, production=True)
        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
            "scheme": "https",
            "server": ("id.vib.tools", 443),
            "client": ("127.0.0.1", 1),
        }
        request = Request(scope)
        response = await middleware.dispatch(
            request, lambda _: asyncio.sleep(0, result=PlainTextResponse("ok"))
        )
        return response

    static = asyncio.run(exercise("/static/app.css"))
    assert "immutable" in static.headers["cache-control"]
    assert "Strict-Transport-Security" in static.headers
    health = asyncio.run(exercise("/health/live"))
    assert health.headers["cache-control"] == "no-store"


def test_oidc_refresh_success_rotation_and_failure_shapes() -> None:
    settings = get_settings()

    class Validator:
        async def metadata(self) -> OIDCMetadata:
            return OIDCMetadata("i", "a", "http://auth.test/token", "j", None)

    responses = [
        httpx.Response(200, json={"access_token": "new-access"}),
        httpx.Response(500),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={"not_access_token": "bad"}),
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return responses.pop(0)

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            oidc = OIDCClient(
                settings,
                http,
                Validator(),  # type: ignore[arg-type]
                TokenCipher(settings.TOKEN_ENCRYPTION_KEY.get_secret_value()),
            )
            refreshed = await oidc.refresh("old-refresh")
            assert refreshed["refresh_token"] == "old-refresh"
            for _ in range(3):
                with pytest.raises(OIDCFlowError):
                    await oidc.refresh("old-refresh")

    asyncio.run(exercise())


def test_runtime_entrypoint_uses_hardened_single_worker_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import run

    captured: dict[str, object] = {}

    def fake_run(application: str, **kwargs: object) -> None:
        captured["application"] = application
        captured.update(kwargs)

    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.0.0.1")
    monkeypatch.setattr(run.uvicorn, "run", fake_run)
    run.main()
    assert captured == {
        "application": "app.main:app",
        "host": "0.0.0.0",  # noqa: S104 - validates container listener
        "port": 8000,
        "workers": 1,
        "proxy_headers": True,
        "forwarded_allow_ips": "10.0.0.1",
        "access_log": False,
        "timeout_graceful_shutdown": 20,
    }
