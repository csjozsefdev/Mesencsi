"""Double-submit CSRF protection middleware."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from grafi_core.settings.cookie_names import CookieNames

CSRF_HEADER = "x-csrf-token"

_DEFAULT_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/health",
    "/dev/",
    "/payments/barion/ipn",
    "/auth/login",
    "/auth/logout",
    "/auth/register",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/auth/verify-email",
    "/auth/csrf",
    "/admin/login",
    "/admin/logout",
)


def issue_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(
    response: Response,
    token: str,
    *,
    secure: bool,
    cookie_names: CookieNames | None = None,
) -> None:
    names = cookie_names or CookieNames()
    response.set_cookie(
        names.csrf,
        token,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


@dataclass(frozen=True)
class CsrfConfig:
    exempt_prefixes: tuple[str, ...] = _DEFAULT_EXEMPT_PREFIXES
    cookie_names: CookieNames | None = None


class CsrfMiddleware(BaseHTTPMiddleware):
    """
    Double-submit CSRF protection.

    For unsafe methods, require cookie + X-CSRF-Token header with an exact match.
    Bearer auth and unauthenticated requests bypass CSRF (endpoint auth handles those).
    """

    def __init__(self, app, config: CsrfConfig | None = None) -> None:
        super().__init__(app)
        self._cfg = config or CsrfConfig()
        self._cookies = self._cfg.cookie_names or CookieNames()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or "/"
        for prefix in self._cfg.exempt_prefixes:
            if path == prefix or path.startswith(prefix):
                return await call_next(request)

        if request.method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            auth = (request.headers.get("authorization") or "").strip().lower()
            if auth.startswith("bearer "):
                return await call_next(request)
            if not (
                request.cookies.get(self._cookies.user_token)
                or request.cookies.get(self._cookies.admin_token)
            ):
                return await call_next(request)
            cookie_token = (request.cookies.get(self._cookies.csrf) or "").strip()
            header_token = (request.headers.get(CSRF_HEADER) or "").strip()
            if not cookie_token or not header_token or cookie_token != header_token:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF protection: missing or invalid token."},
                )

        return await call_next(request)
