"""Portal preference routes."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from io import StringIO
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.account_experience.service import avatar_url_for_key
from app.account_security.service import (
    application_summaries,
    claims_from_auth,
    safe_central_sessions,
)
from app.accounts.repository import (
    get_preferences,
    get_profile,
    list_contacts,
    list_social_links,
    update_preferences,
)
from app.accounts.schemas import validate_timezone
from app.auth.sessions import AuthenticatedSession
from app.database.models.enums import Theme
from app.dependencies import get_db, request_security_context, require_auth, validate_csrf
from app.middleware.rate_limit import RateLimit
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


@router.get("/account-data.txt")
async def account_data_txt(  # pragma: no cover
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> Response:
    """Download a plain-text user account data export."""

    await _record_account_data_export(request, db, auth, export_format="txt")
    rows = await _account_data_export_rows(request, db, auth)
    generated_at = datetime.now(UTC)
    lines = [
        "Vib ID Account Data Export",
        f"Generated at: {generated_at.isoformat()}",
        "",
    ]
    current_section = ""
    for section, key, value in rows:
        if section != current_section:
            if current_section:
                lines.append("")
            lines.append(f"[{section}]")
            current_section = section
        lines.append(f"{key}: {value}")
    content = "\n".join(lines).rstrip() + "\n"
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers=_download_headers("txt", generated_at),
    )


@router.get("/account-data.csv")
async def account_data_csv(  # pragma: no cover
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> Response:
    """Download a CSV user account data export."""

    await _record_account_data_export(request, db, auth, export_format="csv")
    rows = await _account_data_export_rows(request, db, auth)
    generated_at = datetime.now(UTC)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["section", "field", "value"])
    writer.writerow(["Export", "Generated at", generated_at.isoformat()])
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers=_download_headers("csv", generated_at),
    )


@router.post("/quick-theme", response_class=HTMLResponse)
async def quick_theme_update(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> Response:
    """Update only the visual theme from the global quick-settings menu."""

    await validate_csrf(request, auth)
    form = await request.form()
    try:
        theme = Theme(str(form.get("theme", "dark")))
    except ValueError:
        theme = Theme.DARK

    preferences = await get_preferences(db, auth.subject)
    locale = preferences.locale if preferences is not None else "en"
    timezone_name = preferences.timezone if preferences is not None else "UTC"
    security_notifications = (
        preferences.security_email_notifications if preferences is not None else True
    )
    await update_preferences(
        db,
        subject=auth.subject,
        theme=theme,
        locale=locale,
        timezone_name=timezone_name,
        security_notifications=security_notifications,
    )

    ip_value, user_agent = request_security_context(request)
    await record_activity(
        db,
        subject=auth.subject,
        event_type="preferences_changed",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"field_names": ["theme"], "source": "quick-settings"},
    )

    requested_next = str(form.get("next", "/"))
    allowed_paths = {
        "/",
        "/profile",
        "/security",
        "/sessions",
        "/services",
        "/activity",
        "/preferences",
    }
    destination = requested_next if requested_next in allowed_paths else "/"
    return RedirectResponse(destination, status_code=303)


@router.post("", response_class=HTMLResponse)
async def preferences_update(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> Response:
    await validate_csrf(request, auth)
    form = await request.form()
    try:
        theme = Theme(str(form.get("theme", "dark")))
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


async def _record_account_data_export(
    request: Request,
    db: AsyncSession,
    auth: AuthenticatedSession,
    *,
    export_format: str,
) -> None:
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="account-data-export",
        identity=auth.subject,
        limit=RateLimit(5, 3600),
    )
    ip_value, user_agent = request_security_context(request)
    await record_activity(
        db,
        subject=auth.subject,
        event_type="account_data_exported",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"format": export_format, "status": "downloaded"},
    )


async def _account_data_export_rows(
    request: Request,
    db: AsyncSession,
    auth: AuthenticatedSession,
) -> list[tuple[str, str, str]]:
    claims = claims_from_auth(auth)
    profile = await get_profile(db, auth.subject)
    preferences = await get_preferences(db, auth.subject)
    contacts = await list_contacts(db, auth.subject)
    social_links = await list_social_links(db, auth.subject)
    central_raw = await safe_central_sessions(request.app.state.keycloak, auth.subject)
    applications = await application_summaries(db, auth.subject, central_sessions=central_raw)
    avatar_url = avatar_url_for_key(
        request.app.state.settings.APP_BASE_URL,
        profile.avatar_key if profile is not None else None,
    )
    rows: list[tuple[str, str, str]] = [
        ("Account", "Subject", auth.subject),
        (
            "Account",
            "Display name",
            _value(profile.display_name if profile else claims.get("name")),
        ),
        ("Account", "Preferred username", _value(claims.get("preferred_username"))),
        ("Account", "Email", _value(claims.get("email"))),
        ("Account", "Email verified", _value(claims.get("email_verified"))),
        ("Profile", "Phone country code", _value(profile.phone_country_code if profile else None)),
        ("Profile", "Phone number", _value(profile.phone_number if profile else None)),
        ("Profile", "Country code", _value(profile.country_code if profile else None)),
        ("Profile", "Preferred language", _value(profile.preferred_language if profile else None)),
        ("Profile", "Timezone", _value(profile.timezone if profile else None)),
        ("Profile", "Organization", _value(profile.organization_name if profile else None)),
        ("Profile", "Job title", _value(profile.job_title if profile else None)),
        ("Profile", "Avatar URL", _value(avatar_url)),
        ("Profile", "Updated at", _value(profile.updated_at if profile else None)),
        (
            "Preferences",
            "Theme",
            _value(preferences.theme.value if preferences else Theme.DARK.value),
        ),
        ("Preferences", "Locale", _value(preferences.locale if preferences else "en")),
        ("Preferences", "Timezone", _value(preferences.timezone if preferences else "UTC")),
        (
            "Preferences",
            "Security email notifications",
            _value(preferences.security_email_notifications if preferences else True),
        ),
    ]
    for index, contact in enumerate(contacts, start=1):
        rows.extend(
            [
                ("Contacts", f"Contact {index} type", contact.contact_type.value),
                ("Contacts", f"Contact {index} label", contact.label),
                ("Contacts", f"Contact {index} value", contact.value),
                ("Contacts", f"Contact {index} primary", _value(contact.is_primary)),
                ("Contacts", f"Contact {index} verified", _value(contact.is_verified)),
            ]
        )
    if not contacts:
        rows.append(("Contacts", "Saved contacts", "None"))
    for index, link in enumerate(social_links, start=1):
        rows.extend(
            [
                ("Social links", f"Link {index} platform", link.platform),
                ("Social links", f"Link {index} label", link.label),
                ("Social links", f"Link {index} url", link.url),
                ("Social links", f"Link {index} visibility", link.visibility),
            ]
        )
    if not social_links:
        rows.append(("Social links", "Saved social links", "None"))
    for index, application in enumerate(applications, start=1):
        rows.extend(
            [
                ("Applications", f"Application {index} name", application.display_name),
                ("Applications", f"Application {index} domain", application.domain),
                ("Applications", f"Application {index} status", application.status),
                ("Applications", f"Application {index} source", application.source),
                (
                    "Applications",
                    f"Application {index} last activity",
                    _value(application.last_authenticated_at),
                ),
            ]
        )
    if not applications:
        rows.append(("Applications", "Connected application history", "None"))
    return rows


def _download_headers(filetype: str, generated_at: datetime) -> dict[str, str]:
    stamp = generated_at.strftime("%Y%m%d-%H%M%S")
    return {
        "Cache-Control": "no-store",
        "Content-Disposition": f'attachment; filename="vib-id-account-data-{stamp}.{filetype}"',
        "X-Content-Type-Options": "nosniff",
    }


def _value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
