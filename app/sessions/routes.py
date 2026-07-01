"""Local and approved central session management routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.keycloak_management import KeycloakUnavailable
from app.auth.sessions import AuthenticatedSession
from app.dependencies import get_db, request_security_context, require_auth, validate_csrf
from app.middleware.rate_limit import RateLimit
from app.security.audit import record_activity
from app.web import base_context, templates

router = APIRouter(prefix="/sessions")


@router.get("", response_class=HTMLResponse)
async def sessions_page(
    request: Request,
    revoked: int = 0,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    sessions = await request.app.state.session_service.list_active(db, auth.subject)
    central = await request.app.state.keycloak.account_status(auth.subject)
    return templates.TemplateResponse(
        request,
        "sessions/index.html",
        base_context(
            request,
            auth=auth,
            active_nav="sessions",
            sessions=sessions,
            central_status=central,
            revoked=bool(revoked),
        ),
    )


@router.post("/{session_id}/revoke")
async def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    if session_id == auth.model.id:
        raise HTTPException(status_code=400, detail="Use Sign Out to terminate the current session")
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="session-revoke",
        identity=auth.subject,
        limit=RateLimit(20, 300),
    )
    revoked = await request.app.state.session_service.revoke(
        db,
        session_id=session_id,
        subject=auth.subject,
        reason="user-revoked-session",
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="Session not found")
    ip_value, user_agent = request_security_context(request)
    await record_activity(
        db,
        subject=auth.subject,
        event_type="session_revoked",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"target_session": "other-local-session"},
    )
    return RedirectResponse("/sessions?revoked=1", status_code=303)


@router.post("/revoke-all-others")
async def revoke_all_others(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="session-revoke-all",
        identity=auth.subject,
        limit=RateLimit(5, 300),
    )
    count = await request.app.state.session_service.revoke_all_other(
        db, subject=auth.subject, current_id=auth.model.id
    )
    ip_value, user_agent = request_security_context(request)
    await record_activity(
        db,
        subject=auth.subject,
        event_type="session_revoked",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"target_session": "all-other-local-sessions", "status": count},
    )
    return RedirectResponse("/sessions?revoked=1", status_code=303)


@router.post("/sign-out-everywhere")
async def sign_out_everywhere(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="central-logout-all",
        identity=auth.subject,
        limit=RateLimit(3, 600),
    )
    try:
        await request.app.state.keycloak.logout_user(auth.subject)
    except KeycloakUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Central session service is temporarily unavailable"
        ) from exc
    await request.app.state.session_service.revoke_by_oidc_logout(
        db, sid=None, subject=auth.subject
    )
    ip_value, user_agent = request_security_context(request)
    await record_activity(
        db,
        subject=auth.subject,
        event_type="session_revoked",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"target_session": "all-central-and-local-sessions"},
    )
    response = RedirectResponse(
        request.app.state.settings.OIDC_POST_LOGOUT_REDIRECT_URI, status_code=303
    )
    response.delete_cookie(request.app.state.settings.SESSION_COOKIE_NAME, path="/")
    return response
