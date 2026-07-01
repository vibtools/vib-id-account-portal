"""Template rendering helpers."""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import __version__
from app.auth.sessions import AuthenticatedSession

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
template_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(("html", "xml")),
    enable_async=False,
)
templates = Jinja2Templates(env=template_env)


def format_datetime(value: datetime | None, timezone_name: str = "UTC") -> str:
    if value is None:
        return "Not available"
    try:
        from zoneinfo import ZoneInfo

        target: tzinfo = ZoneInfo(timezone_name)
    except Exception:
        target = UTC
    return value.astimezone(target).strftime("%Y-%m-%d %H:%M %Z")


templates.env.filters["datetime"] = format_datetime


def base_context(
    request: Request,
    *,
    auth: AuthenticatedSession | None = None,
    active_nav: str | None = None,
    **values: Any,
) -> dict[str, Any]:
    settings = request.app.state.settings
    claims = auth.token_bundle.get("_id_claims", {}) if auth else {}
    context: dict[str, Any] = {
        "request": request,
        "app_name": settings.APP_NAME,
        "app_version": __version__,
        "app_base_url": settings.APP_BASE_URL,
        "auth": auth,
        "claims": claims if isinstance(claims, dict) else {},
        "active_nav": active_nav,
        "csrf_token": (request.app.state.csrf.token_for_session(auth.raw_id) if auth else None),
        "keycloak_account_url": settings.KEYCLOAK_ACCOUNT_URL,
        "request_id": getattr(request.state, "request_id", ""),
    }
    context.update(values)
    return context
