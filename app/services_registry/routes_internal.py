"""Protected non-browser service connection endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.schemas import ServiceTouchPayload
from app.auth.token_validation import TokenValidationError
from app.database.models.enums import ActivitySeverity
from app.dependencies import get_db, request_security_context
from app.middleware.rate_limit import RateLimit, RateLimitExceeded
from app.security.audit import record_activity
from app.services_registry.repository import touch_connection

router = APIRouter(prefix="/internal/v1", include_in_schema=False)


@router.post("/service-connections/touch", status_code=204)
async def service_connection_touch(
    payload: ServiceTouchPayload,
    request: Request,
    authorization: str | None = Header(default=None, max_length=16384),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = await request.app.state.validator.validate_service_token(token)
        client_id = str(claims["azp"])
        allowed_service_clients = {payload.service_key, f"{payload.service_key}-backend"}
        if client_id not in allowed_service_clients:
            raise TokenValidationError("service client cannot update this service key")
        await request.app.state.rate_limiter.enforce(
            db,
            namespace="service-touch",
            identity=client_id,
            limit=RateLimit(300, 60),
        )
        _connection, created = await touch_connection(
            db,
            subject=payload.subject,
            service_key=payload.service_key,
            authenticated_at=payload.authenticated_at,
        )
    except (TokenValidationError, RateLimitExceeded, LookupError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Request rejected"
        ) from None
    ip_value, user_agent = request_security_context(request)
    await record_activity(
        db,
        subject=payload.subject,
        event_type="service_first_connected" if created else "service_used",
        request_id=request.state.request_id,
        ip_privacy_value=ip_value,
        user_agent_summary=user_agent,
        severity=ActivitySeverity.NOTICE,
        metadata={"service_key": payload.service_key, "client_id": client_id},
    )
