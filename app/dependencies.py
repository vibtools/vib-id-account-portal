"""FastAPI dependencies and request security helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import cast

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.sessions import AuthenticatedSession
from app.database.models.account import UserPreference
from app.security.identifiers import privacy_ip, sanitize_user_agent


@dataclass(frozen=True, slots=True)
class PreferenceSnapshot:
    locale: str
    timezone: str
    theme: object


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.session_factory() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()


async def optional_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedSession | None:
    cookie_name = request.app.state.settings.SESSION_COOKIE_NAME
    raw_id = request.cookies.get(cookie_name)
    auth = cast(
        AuthenticatedSession | None,
        await request.app.state.session_service.resolve(db, raw_id),
    )
    request.state.auth = auth
    preference = None
    if auth is not None:
        preference = (
            await db.execute(select(UserPreference).where(UserPreference.subject == auth.subject))
        ).scalar_one_or_none()
    request.state.preferences = (
        PreferenceSnapshot(
            locale=preference.locale,
            timezone=preference.timezone,
            theme=preference.theme,
        )
        if preference is not None
        else None
    )
    return auth


async def require_auth(
    auth: AuthenticatedSession | None = Depends(optional_auth),
) -> AuthenticatedSession:
    if auth is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return auth


def request_security_context(request: Request) -> tuple[str, str]:
    settings = request.app.state.settings
    client_ip = request.client.host if request.client else None
    ip_value = privacy_ip(client_ip, settings.IP_PRIVACY_KEY.get_secret_value())
    user_agent = sanitize_user_agent(request.headers.get("user-agent"))
    return ip_value, user_agent


async def validate_csrf(request: Request, auth: AuthenticatedSession) -> None:
    form = await request.form()
    supplied = form.get("csrf_token")
    if not isinstance(supplied, str) or not request.app.state.csrf.validate(auth.raw_id, supplied):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
