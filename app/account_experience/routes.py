"""Account experience routes: avatars and portable profile APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.account_experience.service import portable_profile_for_auth, portable_profile_for_subject
from app.accounts.repository import get_profile_photo_by_key
from app.auth.sessions import AuthenticatedSession
from app.auth.token_validation import TokenValidationError
from app.dependencies import get_db, require_auth
from app.middleware.rate_limit import RateLimit, RateLimitExceeded

router = APIRouter()


@router.get("/media/profile-avatars/{avatar_key}")
async def profile_avatar_media(avatar_key: str, db: AsyncSession = Depends(get_db)) -> Response:
    if len(avatar_key) > 96 or any(part in avatar_key for part in ("/", "\\", "..")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile photo not found")
    photo = await get_profile_photo_by_key(db, avatar_key=avatar_key)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile photo not found")
    return Response(
        content=photo.image_bytes,
        media_type=photo.mime_type,
        headers={
            "Cache-Control": "public, max-age=3600, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/api/account/profile/portable")
async def current_portable_profile(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthenticatedSession = Depends(require_auth),
) -> dict[str, object]:
    profile = await portable_profile_for_auth(
        db, auth=auth, app_base_url=request.app.state.settings.APP_BASE_URL
    )
    return profile.model_dump(mode="json")


@router.get("/internal/v1/account-profiles/{subject}")
async def internal_portable_profile(
    subject: str,
    request: Request,
    authorization: str | None = Header(default=None, max_length=16384),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if len(subject) < 3 or len(subject) > 255 or any(char in subject for char in ("/", "\\")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid subject")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = await request.app.state.validator.validate_service_token(token)
        client_id = str(claims["azp"])
        await request.app.state.rate_limiter.enforce(
            db,
            namespace="portable-profile-read",
            identity=client_id,
            limit=RateLimit(600, 60),
        )
    except (TokenValidationError, RateLimitExceeded):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Request rejected"
        ) from None
    profile = await portable_profile_for_subject(
        db,
        subject=subject,
        app_base_url=request.app.state.settings.APP_BASE_URL,
        claims=None,
    )
    return JSONResponse(profile.model_dump(mode="json"))
