"""Application resource lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.auth.keycloak_management import KeycloakManagementClient
from app.auth.oidc import OIDCClient
from app.auth.sessions import SessionService
from app.auth.token_validation import OIDCValidator
from app.config import get_settings
from app.database.session import Database
from app.logging_config import configure_logging
from app.middleware.rate_limit import DatabaseRateLimiter
from app.security.csrf import CSRFProtector
from app.security.encryption import TokenCipher


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    database = Database(settings)
    timeout = httpx.Timeout(settings.OIDC_HTTP_TIMEOUT_SECONDS)
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    http_client = httpx.AsyncClient(
        timeout=timeout, limits=limits, follow_redirects=False, trust_env=False
    )
    cipher = TokenCipher(settings.TOKEN_ENCRYPTION_KEY.get_secret_value())
    validator = OIDCValidator(settings, http_client)

    app.state.settings = settings
    app.state.database = database
    app.state.http_client = http_client
    app.state.cipher = cipher
    app.state.validator = validator
    app.state.oidc = OIDCClient(settings, http_client, validator, cipher)
    app.state.session_service = SessionService(settings, cipher)
    app.state.keycloak = KeycloakManagementClient(settings, http_client, validator)
    app.state.csrf = CSRFProtector(settings.CSRF_SECRET.get_secret_value())
    app.state.rate_limiter = DatabaseRateLimiter(settings.RATE_LIMIT_ENABLED)
    try:
        yield
    finally:
        await http_client.aclose()
        await database.dispose()
