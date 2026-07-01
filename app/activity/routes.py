"""Paginated user activity browser page."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.activity.repository import list_activity
from app.auth.sessions import AuthenticatedSession
from app.dependencies import get_db, require_auth
from app.web import base_context, templates

router = APIRouter(prefix="/activity")


@router.get("", response_class=HTMLResponse)
async def activity_page(
    request: Request,
    page: int = Query(default=1, ge=1, le=10000),
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> HTMLResponse:
    date_from = datetime.now(UTC) - timedelta(days=days)
    records, total = await list_activity(db, subject=auth.subject, page=page, date_from=date_from)
    total_pages = max(1, math.ceil(total / 20))
    if page > total_pages and total > 0:
        raise HTTPException(status_code=404, detail="Activity page not found")
    return templates.TemplateResponse(
        request,
        "activity/index.html",
        base_context(
            request,
            auth=auth,
            active_nav="activity",
            records=records,
            page=page,
            days=days,
            total=total,
            total_pages=total_pages,
        ),
    )
