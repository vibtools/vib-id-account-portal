"""Native user-facing security and applications routes for Vib ID."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.account_security.service import (
    application_catalog_summaries,
    application_summaries,
    central_session_summaries,
    claims_from_auth,
    local_session_summaries,
    profile_summary,
    safe_central_sessions,
    security_status_from_central,
)
from app.auth.keycloak_management import KeycloakUnavailable
from app.auth.sessions import AuthenticatedSession
from app.dependencies import get_db, request_security_context, require_auth, validate_csrf
from app.middleware.rate_limit import RateLimit
from app.security.audit import record_activity
from app.web import base_context, templates

router = APIRouter()


def _security_message(request: Request, key: str) -> str:
    messages = {
        "password_requested": (  # nosec B105
            "A secure credential-change email has been sent if the account can receive it."
        ),
        "verify_email_requested": (
            "A verification email has been sent if the central identity service is available."
        ),
        "email_change_requested": (
            "The email-change request was accepted and verification was requested."
        ),
        "totp_requested": "A secure 2FA setup email has been sent if the account can receive it.",
        "totp_disabled": "Two-factor authenticator credential removal was requested.",
        "session_revoked": "The selected session was revoked.",
        "all_sessions_revoked": "All other portal sessions were revoked.",
        "central_unavailable": (
            "Central identity service is temporarily unavailable. Try again shortly."
        ),
        "unsupported": "This action is not enabled for the current realm capability.",
    }
    del request
    return messages.get(key, "")


async def _central_status(request: Request, auth: AuthenticatedSession) -> Any:
    return await request.app.state.keycloak.account_status(auth.subject)


@router.get("/security/password", response_class=HTMLResponse)
async def password_page(  # pragma: no cover
    request: Request,
    message: str = "",
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    central = await _central_status(request, auth)
    return templates.TemplateResponse(
        request,
        "security/password.html",
        base_context(
            request,
            auth=auth,
            active_nav="security",
            central_status=central,
            message=_security_message(request, message),
        ),
    )


@router.post("/security/password/change-request")
async def password_change_request(  # pragma: no cover
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="password-action-request",
        identity=auth.subject,
        limit=RateLimit(5, 3600),
    )
    ip_value, user_agent = request_security_context(request)
    try:
        await request.app.state.keycloak.execute_required_actions_email(
            auth.subject,
            actions=["UPDATE_PASSWORD"],
            redirect_uri=f"{request.app.state.settings.APP_BASE_URL.rstrip('/')}/security/password",
        )
        message = "password_requested"
    except (AttributeError, KeycloakUnavailable):
        message = "central_unavailable"
    await record_activity(
        db,
        subject=auth.subject,
        event_type="password_change_requested",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"status": message},
    )
    return RedirectResponse(f"/security/password?message={message}", status_code=303)


@router.get("/security/email", response_class=HTMLResponse)
async def email_page(  # pragma: no cover
    request: Request,
    message: str = "",
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    central = await _central_status(request, auth)
    claims = claims_from_auth(auth)
    token_email_verified = bool(claims.get("email_verified")) if isinstance(claims, dict) else False
    return templates.TemplateResponse(
        request,
        "security/email.html",
        base_context(
            request,
            auth=auth,
            active_nav="security",
            central_status=central,
            current_email=claims.get("email") if isinstance(claims.get("email"), str) else None,
            email_verified=(
                central.email_verified
                if central.email_verified is not None
                else token_email_verified
            ),
            message=_security_message(request, message),
            errors=[],
        ),
    )


@router.post("/security/email/resend-verification")
async def resend_email_verification(  # pragma: no cover
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="email-verification-request",
        identity=auth.subject,
        limit=RateLimit(3, 900),
    )
    ip_value, user_agent = request_security_context(request)
    try:
        await request.app.state.keycloak.send_verify_email(
            auth.subject,
            redirect_uri=f"{request.app.state.settings.APP_BASE_URL.rstrip('/')}/security/email",
        )
        message = "verify_email_requested"
    except (AttributeError, KeycloakUnavailable):
        message = "central_unavailable"
    await record_activity(
        db,
        subject=auth.subject,
        event_type="email_verification_requested",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"status": message},
    )
    return RedirectResponse(f"/security/email?message={message}", status_code=303)


@router.post("/security/email/change-request")
async def email_change_request(  # pragma: no cover
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> Response:
    await validate_csrf(request, auth)
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="email-change-request",
        identity=auth.subject,
        limit=RateLimit(3, 3600),
    )
    form = await request.form()
    raw_email = str(form.get("new_email", "")).strip().lower()
    from pydantic import BaseModel, EmailStr

    class _EmailPayload(BaseModel):
        new_email: EmailStr

    try:
        payload = _EmailPayload(new_email=raw_email)
    except ValidationError:
        central = await _central_status(request, auth)
        claims = claims_from_auth(auth)
        return templates.TemplateResponse(
            request,
            "security/email.html",
            base_context(
                request,
                auth=auth,
                active_nav="security",
                central_status=central,
                current_email=claims.get("email") if isinstance(claims.get("email"), str) else None,
                email_verified=central.email_verified,
                message="",
                errors=["Enter a valid email address."],
                form_values=dict(form),
            ),
            status_code=422,
        )
    ip_value, user_agent = request_security_context(request)
    try:
        await request.app.state.keycloak.update_user_email(
            auth.subject,
            str(payload.new_email),
            redirect_uri=f"{request.app.state.settings.APP_BASE_URL.rstrip('/')}/security/email",
        )
        message = "email_change_requested"
    except (AttributeError, KeycloakUnavailable):
        message = "central_unavailable"
    await record_activity(
        db,
        subject=auth.subject,
        event_type="email_change_requested",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"status": message, "field_names": ["email"]},
    )
    return RedirectResponse(f"/security/email?message={message}", status_code=303)


@router.get("/security/2fa", response_class=HTMLResponse)
async def two_factor_page(  # pragma: no cover
    request: Request,
    message: str = "",
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    central = await _central_status(request, auth)
    return templates.TemplateResponse(
        request,
        "security/two_factor.html",
        base_context(
            request,
            auth=auth,
            active_nav="security",
            central_status=central,
            message=_security_message(request, message),
        ),
    )


@router.post("/security/2fa/enable")
async def enable_two_factor(  # pragma: no cover
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="totp-enable-request",
        identity=auth.subject,
        limit=RateLimit(5, 3600),
    )
    ip_value, user_agent = request_security_context(request)
    try:
        await request.app.state.keycloak.execute_required_actions_email(
            auth.subject,
            actions=["CONFIGURE_TOTP"],
            redirect_uri=f"{request.app.state.settings.APP_BASE_URL.rstrip('/')}/security/2fa",
        )
        message = "totp_requested"
    except (AttributeError, KeycloakUnavailable):
        message = "central_unavailable"
    await record_activity(
        db,
        subject=auth.subject,
        event_type="mfa_enable_requested",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"status": message},
    )
    return RedirectResponse(f"/security/2fa?message={message}", status_code=303)


@router.post("/security/2fa/disable")
async def disable_two_factor(  # pragma: no cover
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="totp-disable-request",
        identity=auth.subject,
        limit=RateLimit(3, 3600),
    )
    ip_value, user_agent = request_security_context(request)
    try:
        disabled = await request.app.state.keycloak.remove_totp_credentials(auth.subject)
        message = "totp_disabled" if disabled else "unsupported"
    except (AttributeError, KeycloakUnavailable):
        message = "central_unavailable"
    await record_activity(
        db,
        subject=auth.subject,
        event_type="mfa_disable_requested",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"status": message},
    )
    return RedirectResponse(f"/security/2fa?message={message}", status_code=303)


@router.get("/security/recovery-codes", response_class=HTMLResponse)
async def recovery_codes_page(  # pragma: no cover
    request: Request,
    message: str = "",
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    central = await _central_status(request, auth)
    return templates.TemplateResponse(
        request,
        "security/recovery_codes.html",
        base_context(
            request,
            auth=auth,
            active_nav="security",
            central_status=central,
            message=_security_message(request, message),
        ),
    )


@router.get("/security/sessions", response_class=HTMLResponse)
async def security_sessions_page(  # pragma: no cover
    request: Request,
    revoked: int = 0,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    local_sessions = await request.app.state.session_service.list_active(db, auth.subject)
    central = await _central_status(request, auth)
    central_raw = await safe_central_sessions(request.app.state.keycloak, auth.subject)
    return templates.TemplateResponse(
        request,
        "security/sessions.html",
        base_context(
            request,
            auth=auth,
            active_nav="sessions",
            sessions=local_sessions,
            central_status=central,
            central_sessions=central_session_summaries(central_raw),
            revoked=bool(revoked),
        ),
    )


@router.post("/security/sessions/{session_id}/revoke")
async def security_revoke_session(  # pragma: no cover
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
        namespace="security-session-revoke",
        identity=auth.subject,
        limit=RateLimit(20, 300),
    )
    revoked = await request.app.state.session_service.revoke(
        db,
        session_id=session_id,
        subject=auth.subject,
        reason="user-revoked-session-security-module",
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
        metadata={"target_session": "other-local-session", "status": "security-module"},
    )
    return RedirectResponse("/security/sessions?revoked=1", status_code=303)


@router.post("/security/sessions/logout-all")
async def security_logout_all(  # pragma: no cover
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="security-session-revoke-all",
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
    return RedirectResponse("/security/sessions?revoked=1", status_code=303)


@router.get("/applications", response_class=HTMLResponse)
async def applications_page(  # pragma: no cover
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    central_raw = await safe_central_sessions(request.app.state.keycloak, auth.subject)
    connections = await application_summaries(db, auth.subject, central_sessions=central_raw)
    available_apps = application_catalog_summaries(connections)
    return templates.TemplateResponse(
        request,
        "applications/index.html",
        base_context(
            request,
            auth=auth,
            active_nav="applications",
            available_apps=available_apps,
            connections=connections,
        ),
    )


@router.get("/api/account/profile")
async def api_profile(  # pragma: no cover
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> dict[str, Any]:
    summary = await profile_summary(db, auth)
    return summary.model_dump()


@router.get("/api/security/status")
async def api_security_status(  # pragma: no cover
    request: Request,
    auth: AuthenticatedSession = Depends(require_auth),
) -> dict[str, Any]:
    central = await _central_status(request, auth)
    claims = claims_from_auth(auth)
    token_email_verified = bool(claims.get("email_verified")) if isinstance(claims, dict) else None
    return security_status_from_central(
        central, token_email_verified=token_email_verified
    ).model_dump()


@router.get("/api/security/2fa/status")
async def api_two_factor_status(  # pragma: no cover
    request: Request,
    auth: AuthenticatedSession = Depends(require_auth),
) -> dict[str, bool | None]:
    central = await _central_status(request, auth)
    return {"enabled": central.two_factor_enabled, "available": central.available}


@router.get("/api/security/sessions")
async def api_security_sessions(  # pragma: no cover
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> dict[str, Any]:
    sessions = await request.app.state.session_service.list_active(db, auth.subject)
    central_raw = await safe_central_sessions(request.app.state.keycloak, auth.subject)
    return {
        "local": [item.model_dump(mode="json") for item in local_session_summaries(auth, sessions)],
        "central": [
            item.model_dump(mode="json") for item in central_session_summaries(central_raw)
        ],
    }


@router.get("/api/applications")
async def api_applications(  # pragma: no cover
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> dict[str, Any]:
    central_raw = await safe_central_sessions(request.app.state.keycloak, auth.subject)
    applications = await application_summaries(db, auth.subject, central_sessions=central_raw)
    return {"applications": [item.model_dump(mode="json") for item in applications]}


@router.delete("/api/applications/{client_id}/consent")
async def api_revoke_application_consent(  # pragma: no cover
    client_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> JSONResponse:
    if len(client_id) > 128 or any(part in client_id.lower() for part in ("..", "/", "\\")):
        raise HTTPException(status_code=400, detail="Invalid client id")
    csrf = request.headers.get("x-csrf-token")
    if not csrf or not request.app.state.csrf.validate(auth.raw_id, csrf):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="application-consent-revoke",
        identity=auth.subject,
        limit=RateLimit(10, 3600),
    )
    ip_value, user_agent = request_security_context(request)
    try:
        revoked = await request.app.state.keycloak.revoke_user_consent(auth.subject, client_id)
    except (AttributeError, KeycloakUnavailable):
        revoked = False
    await record_activity(
        db,
        subject=auth.subject,
        event_type="application_consent_revoked",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"client_id": client_id, "status": bool(revoked)},
    )
    return JSONResponse({"revoked": bool(revoked)})
