"""Overview, profile, and contact browser routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.account_experience.profile_media import AvatarValidationError, read_avatar_upload
from app.account_experience.service import avatar_url_for_key
from app.accounts.repository import (
    ConcurrentProfileUpdate,
    add_contact,
    delete_contact,
    delete_profile_photo,
    delete_social_link,
    get_preferences,
    get_profile,
    list_contacts,
    list_social_links,
    update_profile,
    upsert_profile_photo,
    upsert_social_link,
)
from app.accounts.schemas import ContactCreate, ProfileUpdate, SocialLinkPayload
from app.accounts.service import profile_completeness
from app.activity.repository import latest_activity
from app.auth.sessions import AuthenticatedSession
from app.dependencies import get_db, request_security_context, require_auth, validate_csrf
from app.middleware.rate_limit import RateLimit
from app.security.audit import record_activity
from app.services_registry.repository import list_user_connections
from app.web import base_context, templates

router = APIRouter()


def _avatar_url(request: Request, profile: object | None) -> str | None:
    avatar_key = getattr(profile, "avatar_key", None)
    return avatar_url_for_key(request.app.state.settings.APP_BASE_URL, avatar_key)


@router.get("/", response_class=HTMLResponse)
async def overview(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    profile = await get_profile(db, auth.subject)
    preferences = await get_preferences(db, auth.subject)
    connections = await list_user_connections(db, auth.subject)
    local_sessions = await request.app.state.session_service.list_active(db, auth.subject)
    latest = await latest_activity(db, auth.subject)
    central = await request.app.state.keycloak.account_status(auth.subject)
    claims = auth.token_bundle.get("_id_claims", {})
    token_email_verified = bool(claims.get("email_verified")) if isinstance(claims, dict) else False
    email_verified = (
        central.email_verified if central.email_verified is not None else token_email_verified
    )
    recommendations: list[str] = []
    if not email_verified:
        recommendations.append("Verify your primary email through Vib ID security settings.")
    if central.two_factor_enabled is False:
        recommendations.append("Enable two-factor authentication for stronger account security.")
    if profile_completeness(profile) < 70:
        recommendations.append("Complete your profile and contact information.")
    return templates.TemplateResponse(
        request,
        "overview/index.html",
        base_context(
            request,
            auth=auth,
            active_nav="overview",
            profile=profile,
            preferences=preferences,
            completeness=profile_completeness(profile),
            connected_count=len(connections),
            local_session_count=len(local_sessions),
            central_status=central,
            latest_activity=latest,
            recommendations=recommendations,
            email_verified=email_verified,
            avatar_url=_avatar_url(request, profile),
        ),
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    saved: int = 0,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    profile = await get_profile(db, auth.subject)
    contacts = await list_contacts(db, auth.subject)
    social_links = await list_social_links(db, auth.subject)
    avatar_url = _avatar_url(request, profile)
    return templates.TemplateResponse(
        request,
        "profile/index.html",
        base_context(
            request,
            auth=auth,
            active_nav="profile",
            profile=profile,
            contacts=contacts,
            social_links=social_links,
            avatar_url=avatar_url,
            timezones=sorted(available_timezones()),
            saved=bool(saved),
            errors=[],
            contact_errors=[],
            social_errors=[],
        ),
    )


@router.post("/profile", response_class=HTMLResponse)
async def profile_update(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> Response:
    await validate_csrf(request, auth)
    ip_value, user_agent = request_security_context(request)
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="profile-update",
        identity=auth.subject,
        limit=RateLimit(20, 300),
    )
    form = await request.form()
    try:
        payload = ProfileUpdate(
            display_name=str(form.get("display_name", "")),
            phone_number=str(form.get("phone_number", "")) or None,
            phone_country_code=str(form.get("phone_country_code", "")) or None,
            country_code=str(form.get("country_code", "")) or None,
            timezone=str(form.get("timezone", "UTC")),
            preferred_language=str(form.get("preferred_language", "en")),
            organization_name=str(form.get("organization_name", "")) or None,
            job_title=str(form.get("job_title", "")) or None,
            version=datetime.fromisoformat(str(form.get("version", ""))),
        )
        updated = await update_profile(db, subject=auth.subject, payload=payload)
    except (ValidationError, ValueError, ConcurrentProfileUpdate) as exc:
        profile = await get_profile(db, auth.subject)
        contacts = await list_contacts(db, auth.subject)
        errors = (
            [item["msg"] for item in exc.errors()]
            if isinstance(exc, ValidationError)
            else [str(exc)]
        )
        return templates.TemplateResponse(
            request,
            "profile/index.html",
            base_context(
                request,
                auth=auth,
                active_nav="profile",
                profile=profile,
                contacts=contacts,
                social_links=await list_social_links(db, auth.subject),
                avatar_url=_avatar_url(request, profile),
                timezones=sorted(available_timezones()),
                saved=False,
                errors=errors,
                contact_errors=[],
                social_errors=[],
                form_values=dict(form),
            ),
            status_code=422,
        )
    await record_activity(
        db,
        subject=auth.subject,
        event_type="profile_changed",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"field_names": ["profile"], "status": str(updated.id)},
    )
    return RedirectResponse("/profile?saved=1", status_code=303)


@router.post("/profile/avatar")
async def profile_avatar_update(
    request: Request,
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> Response:
    await validate_csrf(request, auth)
    ip_value, user_agent = request_security_context(request)
    await request.app.state.rate_limiter.enforce(
        db, namespace="profile-avatar-update", identity=auth.subject, limit=RateLimit(10, 3600)
    )
    try:
        avatar = await read_avatar_upload(
            photo,
            max_bytes=request.app.state.settings.PROFILE_AVATAR_MAX_BYTES,
            allowed_types=request.app.state.settings.allowed_profile_avatar_types,
        )
        await upsert_profile_photo(
            db,
            subject=auth.subject,
            avatar_key=avatar.avatar_key,
            mime_type=avatar.mime_type,
            size_bytes=avatar.size_bytes,
            sha256_hash=avatar.sha256_hash,
            image_bytes=avatar.image_bytes,
        )
    except AvatarValidationError as exc:
        profile = await get_profile(db, auth.subject)
        contacts = await list_contacts(db, auth.subject)
        return templates.TemplateResponse(
            request,
            "profile/index.html",
            base_context(
                request,
                auth=auth,
                active_nav="profile",
                profile=profile,
                contacts=contacts,
                social_links=await list_social_links(db, auth.subject),
                avatar_url=_avatar_url(request, profile),
                timezones=sorted(available_timezones()),
                saved=False,
                errors=[str(exc)],
                contact_errors=[],
                social_errors=[],
            ),
            status_code=422,
        )
    await record_activity(
        db,
        subject=auth.subject,
        event_type="profile_avatar_changed",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"status": "uploaded", "bytes": avatar.size_bytes, "mime_type": avatar.mime_type},
    )
    return RedirectResponse("/profile?saved=1", status_code=303)


@router.post("/profile/avatar/delete")
async def profile_avatar_delete(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    await delete_profile_photo(db, subject=auth.subject)
    ip_value, user_agent = request_security_context(request)
    await record_activity(
        db,
        subject=auth.subject,
        event_type="profile_avatar_changed",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"status": "removed"},
    )
    return RedirectResponse("/profile?saved=1", status_code=303)


@router.post("/profile/social-links")
async def social_link_upsert(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> Response:
    await validate_csrf(request, auth)
    ip_value, user_agent = request_security_context(request)
    await request.app.state.rate_limiter.enforce(
        db, namespace="profile-social-update", identity=auth.subject, limit=RateLimit(30, 300)
    )
    form = await request.form()
    try:
        payload = SocialLinkPayload(
            platform=str(form.get("platform", "")),
            label=str(form.get("label", "")),
            url=str(form.get("url", "")),
            visibility=str(form.get("visibility", "apps")),
        )
        await upsert_social_link(db, subject=auth.subject, payload=payload)
    except (ValidationError, ValueError) as exc:
        profile = await get_profile(db, auth.subject)
        contacts = await list_contacts(db, auth.subject)
        errors = (
            [item["msg"] for item in exc.errors()]
            if isinstance(exc, ValidationError)
            else [str(exc)]
        )
        return templates.TemplateResponse(
            request,
            "profile/index.html",
            base_context(
                request,
                auth=auth,
                active_nav="profile",
                profile=profile,
                contacts=contacts,
                social_links=await list_social_links(db, auth.subject),
                avatar_url=_avatar_url(request, profile),
                timezones=sorted(available_timezones()),
                saved=False,
                errors=[],
                contact_errors=[],
                social_errors=errors,
            ),
            status_code=422,
        )
    await record_activity(
        db,
        subject=auth.subject,
        event_type="social_link_changed",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"platform": payload.platform, "visibility": payload.visibility},
    )
    return RedirectResponse("/profile?saved=1", status_code=303)


@router.post("/profile/social-links/{link_id}/delete")
async def social_link_delete(
    link_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    deleted = await delete_social_link(db, subject=auth.subject, link_id=link_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social link not found")
    ip_value, user_agent = request_security_context(request)
    await record_activity(
        db,
        subject=auth.subject,
        event_type="social_link_changed",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"status": "removed"},
    )
    return RedirectResponse("/profile?saved=1", status_code=303)


@router.post("/profile/contacts")
async def contact_create(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> Response:
    await validate_csrf(request, auth)
    ip_value, user_agent = request_security_context(request)
    await request.app.state.rate_limiter.enforce(
        db,
        namespace="contact-update",
        identity=auth.subject,
        limit=RateLimit(30, 300),
    )
    form = await request.form()
    try:
        payload = ContactCreate(
            contact_type=str(form.get("contact_type", "")),
            label=str(form.get("label", "")),
            value=str(form.get("value", "")),
            is_primary=form.get("is_primary") == "on",
        )
        await add_contact(
            db,
            subject=auth.subject,
            payload=payload,
            contact_limit=request.app.state.settings.PROFILE_CONTACT_LIMIT,
        )
    except (ValidationError, ValueError, IntegrityError) as exc:
        await db.rollback()
        profile = await get_profile(db, auth.subject)
        contacts = await list_contacts(db, auth.subject)
        errors = (
            [item["msg"] for item in exc.errors()]
            if isinstance(exc, ValidationError)
            else ["Contact already exists or is invalid."]
        )
        return templates.TemplateResponse(
            request,
            "profile/index.html",
            base_context(
                request,
                auth=auth,
                active_nav="profile",
                profile=profile,
                contacts=contacts,
                social_links=await list_social_links(db, auth.subject),
                avatar_url=_avatar_url(request, profile),
                timezones=sorted(available_timezones()),
                saved=False,
                errors=[],
                contact_errors=errors,
                social_errors=[],
            ),
            status_code=422,
        )
    await record_activity(
        db,
        subject=auth.subject,
        event_type="contact_changed",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"field_names": ["contact"]},
    )
    return RedirectResponse("/profile?saved=1", status_code=303)


@router.post("/profile/contacts/{contact_id}/delete")
async def contact_remove(
    contact_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> RedirectResponse:
    await validate_csrf(request, auth)
    deleted = await delete_contact(db, subject=auth.subject, contact_id=contact_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    ip_value, user_agent = request_security_context(request)
    await record_activity(
        db,
        subject=auth.subject,
        event_type="contact_changed",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        metadata={"field_names": ["contact-delete"]},
    )
    return RedirectResponse("/profile?saved=1", status_code=303)
