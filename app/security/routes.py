"""Security overview routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.activity.repository import list_activity
from app.auth.sessions import AuthenticatedSession
from app.dependencies import get_db, require_auth
from app.web import base_context, templates

router = APIRouter(prefix="/security")


@router.get("", response_class=HTMLResponse)
async def security_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    central = await request.app.state.keycloak.account_status(auth.subject)
    activities, _ = await list_activity(db, subject=auth.subject, page=1, page_size=5)
    claims = auth.token_bundle.get("_id_claims", {})
    token_email_verified = bool(claims.get("email_verified")) if isinstance(claims, dict) else False
    email_verified = (
        central.email_verified if central.email_verified is not None else token_email_verified
    )
    return templates.TemplateResponse(
        request,
        "security/index.html",
        base_context(
            request,
            auth=auth,
            active_nav="security",
            central_status=central,
            activities=activities,
            email_verified=email_verified,
        ),
    )
