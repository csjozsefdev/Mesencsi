"""Baseline HTTP security headers for HTML, API, and static responses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from fastapi import FastAPI

# Safe for JSON APIs and static assets; does not affect redirect Location targets.
SECURITY_HEADER_VALUES: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def apply_security_headers(response: Response) -> None:
    """Attach production-safe security headers to a Starlette response."""
    for name, value in SECURITY_HEADER_VALUES.items():
        response.headers[name] = value


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply security headers to every response that passes through the app stack."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        apply_security_headers(response)
        return response


def register_security_headers(app: FastAPI) -> None:
    """Register middleware. Call after other ``add_middleware`` calls so headers are outermost on the response."""
    app.add_middleware(SecurityHeadersMiddleware)
