"""Liveness and dependency-aware readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    database_state = "unavailable"
    oidc_state = "unavailable"
    try:
        async with request.app.state.database.session_factory() as db:
            await db.execute(text("SELECT 1"))
            database_state = "ok"
    except Exception:
        database_state = "unavailable"
    try:
        await request.app.state.validator.metadata()
        oidc_state = "ok"
    except Exception:
        oidc_state = "unavailable"
    ready_state = database_state == "ok" and oidc_state == "ok"
    return JSONResponse(
        {
            "status": "ready" if ready_state else "not-ready",
            "database": database_state,
            "oidc": oidc_state,
        },
        status_code=200 if ready_state else 503,
    )
