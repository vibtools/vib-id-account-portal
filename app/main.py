"""Vib ID FastAPI application factory."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import __version__
from app.accounts.routes import router as accounts_router
from app.activity.routes import router as activity_router
from app.auth.routes import router as auth_router
from app.config import get_settings
from app.health.routes import router as health_router
from app.lifespan import lifespan
from app.middleware.body_limit import RequestBodyLimitMiddleware
from app.middleware.rate_limit import RateLimitExceeded
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.preferences.routes import router as preferences_router
from app.security.routes import router as security_router
from app.services_registry.routes import router as services_router
from app.services_registry.routes_internal import router as internal_router
from app.sessions.routes import router as sessions_router
from app.web import base_context, templates

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Vib ID",
        version=__version__,
        docs_url=None if settings.APP_ENV == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.APP_ENV == "production" else "/openapi.json",
        lifespan=lifespan,
    )
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    application.add_middleware(GZipMiddleware, minimum_size=1024)
    application.add_middleware(
        SecurityHeadersMiddleware, production=settings.APP_ENV == "production"
    )
    application.add_middleware(RequestIDMiddleware)
    application.add_middleware(RequestBodyLimitMiddleware, max_bytes=64 * 1024)
    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(accounts_router)
    application.include_router(security_router)
    application.include_router(sessions_router)
    application.include_router(services_router)
    application.include_router(activity_router)
    application.include_router(preferences_router)
    application.include_router(internal_router)

    @application.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> HTMLResponse | JSONResponse | RedirectResponse:
        if exc.status_code == 401 and not request.url.path.startswith(("/internal/", "/health/")):
            return RedirectResponse("/login", status_code=303)
        if request.url.path.startswith(("/internal/", "/health/")):
            return JSONResponse(
                {"detail": str(exc.detail), "request_id": getattr(request.state, "request_id", "")},
                status_code=exc.status_code,
                headers=exc.headers,
            )
        template_name = "errors/404.html" if exc.status_code == 404 else "errors/generic.html"
        return templates.TemplateResponse(
            request,
            template_name,
            base_context(
                request,
                auth=getattr(request.state, "auth", None),
                status_code=exc.status_code,
                message=str(exc.detail),
            ),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.info(
            "Request validation rejected",
            extra={"request_id": getattr(request.state, "request_id", "")},
        )
        return JSONResponse(
            {
                "detail": "Request validation failed",
                "request_id": getattr(request.state, "request_id", ""),
            },
            status_code=422,
        )

    @application.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            {"detail": "Too many requests", "request_id": getattr(request.state, "request_id", "")},
            status_code=429,
            headers={"Retry-After": str(exc.retry_after)},
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> HTMLResponse | JSONResponse:
        logger.exception(
            "Unhandled application error",
            extra={"request_id": getattr(request.state, "request_id", "")},
        )
        if request.url.path.startswith(("/internal/", "/health/")):
            return JSONResponse(
                {
                    "detail": "Internal server error",
                    "request_id": getattr(request.state, "request_id", ""),
                },
                status_code=500,
            )
        return templates.TemplateResponse(
            request,
            "errors/500.html",
            base_context(request, auth=getattr(request.state, "auth", None)),
            status_code=500,
        )

    return application


app = create_app()
