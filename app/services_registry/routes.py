"""Read-only connected-services browser page."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.sessions import AuthenticatedSession
from app.dependencies import get_db, require_auth
from app.services_registry.repository import list_user_connections
from app.web import base_context, templates

router = APIRouter(prefix="/services")


@router.get("", response_class=HTMLResponse)
async def connected_services(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    connections = await list_user_connections(db, auth.subject)
    return templates.TemplateResponse(
        request,
        "services/index.html",
        base_context(
            request,
            auth=auth,
            active_nav="services",
            connections=connections,
        ),
    )
