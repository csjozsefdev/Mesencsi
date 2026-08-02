"""Baseline HTTP security headers for HTML, API, and static responses."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from grafi_core.settings.core_settings import CoreSettings

if TYPE_CHECKING:
    from fastapi import FastAPI

SECURITY_HEADER_VALUES: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "img-src 'self' data: https: ; "
        "script-src 'self' 'unsafe-inline' https://pixel.barion.com; "
        "style-src 'self' 'unsafe-inline' ; "
        "connect-src 'self' https:;"
	"frame-src https://pixel.barion.com;"
    ),
}


def _content_security_policy(is_production: Callable[[], bool]) -> str:
    base = SECURITY_HEADER_VALUES["Content-Security-Policy"]
    if is_production():
        return base + " upgrade-insecure-requests;"
    return base


def apply_security_headers(
    response: Response,
    *,
    is_production: Callable[[], bool] | None = None,
    core_settings: CoreSettings | None = None,
) -> None:
    """Attach production-safe security headers to a Starlette response."""
    prod_check = is_production or (core_settings or CoreSettings.from_env()).is_production
    for name, value in SECURITY_HEADER_VALUES.items():
        if name == "Content-Security-Policy":
            response.headers[name] = _content_security_policy(prod_check)
        else:
            response.headers[name] = value
    if prod_check():
        response.headers["Strict-Transport-Security"] = "max-age=15552000; includeSubDomains"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply security headers to every response that passes through the app stack."""

    def __init__(
        self,
        app,
        *,
        is_production: Callable[[], bool] | None = None,
        core_settings: CoreSettings | None = None,
    ) -> None:
        super().__init__(app)
        self._is_production = is_production or (core_settings or CoreSettings.from_env()).is_production

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        apply_security_headers(response, is_production=self._is_production)
        return response


def register_security_headers(
    app: FastAPI,
    *,
    is_production: Callable[[], bool] | None = None,
    core_settings: CoreSettings | None = None,
) -> None:
    """Register middleware. Call after other add_middleware calls so headers are outermost on the response."""
    app.add_middleware(
        SecurityHeadersMiddleware,
        is_production=is_production,
        core_settings=core_settings,
    )
