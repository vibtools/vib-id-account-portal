"""Security and privacy response headers."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, production: bool) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.production = production

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault(
            "Content-Security-Policy",
            "; ".join(
                (
                    "default-src 'self'",
                    "script-src 'self'",
                    "style-src 'self'",
                    "img-src 'self' data:",
                    "font-src 'self'",
                    "connect-src 'self' https://auth.vib.tools",
                    "frame-ancestors 'none'",
                    "object-src 'none'",
                    "base-uri 'self'",
                    "form-action 'self' https://auth.vib.tools",
                    "upgrade-insecure-requests" if self.production else "block-all-mixed-content",
                )
            ),
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if self.production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"
            )
        if request.url.path.startswith("/static/"):
            response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
        elif request.url.path.startswith("/health/"):
            response.headers.setdefault("Cache-Control", "no-store")
        else:
            response.headers.setdefault(
                "Cache-Control", "no-store, no-cache, must-revalidate, private"
            )
            response.headers.setdefault("Pragma", "no-cache")
        return response
