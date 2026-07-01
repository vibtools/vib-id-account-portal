"""Interactive authentication and back-channel logout routes."""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.repository import ensure_account_records
from app.auth.backchannel_logout import LogoutReplayError, process_logout_token
from app.auth.oidc import OIDCFlowError
from app.auth.sessions import AuthenticatedSession
from app.auth.token_validation import TokenValidationError
from app.database.models.enums import ActivityResult, ActivitySeverity
from app.dependencies import (
    get_db,
    optional_auth,
    request_security_context,
    require_auth,
    validate_csrf,
)
from app.middleware.rate_limit import RateLimit, RateLimitExceeded
from app.security.audit import record_activity
from app.web import base_context, templates

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/login")
async def login(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    ip_value, _ = request_security_context(request)
    try:
        await request.app.state.rate_limiter.enforce(
            db,
            namespace="login",
            identity=ip_value,
            limit=RateLimit(20, 300),
        )
        location = await request.app.state.oidc.begin_login(db)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    return RedirectResponse(location, status_code=status.HTTP_302_FOUND)


@router.get("/auth/callback")
async def auth_callback(
    request: Request,
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
    existing: AuthenticatedSession | None = Depends(optional_auth),
) -> RedirectResponse:
    ip_value, user_agent = request_security_context(request)
    if error or not state or not code:
        await record_activity(
            db,
            subject=None,
            event_type="login_failed",
            request_id=request.state.request_id,
            ip_privacy_value=ip_value,
            user_agent_summary=user_agent,
            result=ActivityResult.FAILURE,
            severity=ActivitySeverity.WARNING,
            metadata={"reason": "provider-error-or-missing-parameters"},
        )
        return RedirectResponse("/auth/error", status_code=303)
    try:
        await request.app.state.rate_limiter.enforce(
            db,
            namespace="callback",
            identity=ip_value,
            limit=RateLimit(30, 300),
        )
        token_bundle, claims = await request.app.state.oidc.complete_login(
            db, state=state, code=code
        )
        subject = str(claims["sub"])
        token_bundle["_id_claims"] = claims
        if existing is not None:
            await request.app.state.session_service.revoke(
                db,
                session_id=existing.model.id,
                subject=existing.subject,
                reason="session-rotation-after-login",
            )
        auth = await request.app.state.session_service.create(
            db,
            subject=subject,
            token_bundle=token_bundle,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
            oidc_sid=str(claims.get("sid")) if claims.get("sid") else None,
        )
        await ensure_account_records(
            db,
            subject=subject,
            display_name=str(
                claims.get("name") or claims.get("preferred_username") or "Vib ID user"
            ),
            locale=str(claims.get("locale") or "en"),
        )
        await record_activity(
            db,
            subject=subject,
            event_type="login_completed",
            request_id=request.state.request_id,
            ip_privacy_value=ip_value,
            user_agent_summary=user_agent,
        )
    except (OIDCFlowError, TokenValidationError, RateLimitExceeded, httpx.HTTPError) as exc:
        logger.warning("OIDC callback rejected", extra={"request_id": request.state.request_id})
        await record_activity(
            db,
            subject=None,
            event_type="login_failed",
            request_id=request.state.request_id,
            ip_privacy_value=ip_value,
            user_agent_summary=user_agent,
            result=ActivityResult.FAILURE,
            severity=ActivitySeverity.WARNING,
            metadata={"reason": type(exc).__name__},
        )
        return RedirectResponse("/auth/error", status_code=303)

    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    settings = request.app.state.settings
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        auth.raw_id,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
        max_age=settings.SESSION_ABSOLUTE_HOURS * 3600,
    )
    return response


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    ip_value, user_agent = request_security_context(request)
    await request.app.state.session_service.revoke(
        db,
        session_id=auth.model.id,
        subject=auth.subject,
        reason="user-logout",
    )
    await record_activity(
        db,
        subject=auth.subject,
        event_type="logout_completed",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
    )
    destination = request.app.state.settings.OIDC_POST_LOGOUT_REDIRECT_URI
    try:
        metadata = await request.app.state.validator.metadata()
    except (TokenValidationError, httpx.HTTPError):
        metadata = None
    if (
        metadata is not None
        and metadata.end_session_endpoint
        and isinstance(auth.token_bundle.get("id_token"), str)
    ):
        params = urlencode(
            {
                "id_token_hint": auth.token_bundle["id_token"],
                "post_logout_redirect_uri": destination,
                "client_id": request.app.state.settings.OIDC_CLIENT_ID,
            }
        )
        destination = f"{metadata.end_session_endpoint}?{params}"
    response = RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(
        request.app.state.settings.SESSION_COOKIE_NAME,
        path="/",
        secure=request.app.state.settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite=request.app.state.settings.SESSION_COOKIE_SAMESITE,
    )
    return response


@router.post("/auth/backchannel-logout")
async def backchannel_logout(
    request: Request,
    logout_token: str = Form(..., max_length=16384),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    try:
        await process_logout_token(
            db,
            token=logout_token,
            validator=request.app.state.validator,
            sessions=request.app.state.session_service,
        )
    except (TokenValidationError, LogoutReplayError):
        raise HTTPException(status_code=400, detail="Invalid logout token") from None
    return HTMLResponse("", status_code=200)


@router.get("/auth/error", response_class=HTMLResponse)
async def auth_error(
    request: Request,
    auth: AuthenticatedSession | None = Depends(optional_auth),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "auth/error.html",
        base_context(request, auth=auth),
        status_code=400,
    )
