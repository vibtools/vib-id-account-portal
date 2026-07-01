"""Portal preference routes."""

from __future__ import annotations

from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.repository import get_preferences, update_preferences
from app.accounts.schemas import validate_timezone
from app.auth.sessions import AuthenticatedSession
from app.database.models.enums import Theme
from app.dependencies import get_db, request_security_context, require_auth, validate_csrf
from app.security.audit import record_activity
from app.web import base_context, templates

router = APIRouter(prefix="/preferences")


@router.get("", response_class=HTMLResponse)
async def preferences_page(
    request: Request,
    saved: int = 0,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    preferences = await get_preferences(db, auth.subject)
    return templates.TemplateResponse(
        request,
        "preferences/index.html",
        base_context(
            request,
            auth=auth,
            active_nav="preferences",
            preferences=preferences,
            timezones=sorted(available_timezones()),
            saved=bool(saved),
            errors=[],
        ),
    )


@router.post("", response_class=HTMLResponse)
async def preferences_update(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> Response:
    await validate_csrf(request, auth)
    form = await request.form()
    try:
        theme = Theme(str(form.get("theme", "system")))
        locale = str(form.get("locale", "en")).strip()
        if not locale or len(locale) > 16:
            raise ValueError("Language setting is invalid")
        timezone_name = validate_timezone(str(form.get("timezone", "UTC")))
        security_notifications = form.get("security_notifications") == "on"
        await update_preferences(
            db,
            subject=auth.subject,
            theme=theme,
            locale=locale,
            timezone_name=timezone_name,
            security_notifications=security_notifications,
        )
    except ValueError as exc:
        preferences = await get_preferences(db, auth.subject)
        return templates.TemplateResponse(
            request,
            "preferences/index.html",
            base_context(
                request,
                auth=auth,
                active_nav="preferences",
                preferences=preferences,
                timezones=sorted(available_timezones()),
                saved=False,
                errors=[str(exc)],
            ),
            status_code=422,
        )
    ip_value, user_agent = request_security_context(request)
    await record_activity(
        db,
        subject=auth.subject,
        event_type="preferences_changed",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"field_names": ["theme", "locale", "timezone", "security-notifications"]},
    )
    return RedirectResponse("/preferences?saved=1", status_code=303)
