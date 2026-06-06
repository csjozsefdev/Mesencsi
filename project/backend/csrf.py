

"""CSRF middleware — delegates to grafi_core with Mesencsi cookie names."""

from __future__ import annotations

from mesencsi_settings import mesencsi_cookie_names
from grafi_core.security.csrf import CSRF_HEADER, CsrfConfig, issue_csrf_token
from grafi_core.security.csrf import CsrfMiddleware as _CsrfMiddleware
from grafi_core.security.csrf import set_csrf_cookie as _set_csrf_cookie
from starlette.responses import Response

CSRF_COOKIE = mesencsi_cookie_names().csrf

_DEFAULT_CONFIG = CsrfConfig(cookie_names=mesencsi_cookie_names())


def set_csrf_cookie(response: Response, token: str, *, secure: bool) -> None:
    _set_csrf_cookie(response, token, secure=secure, cookie_names=mesencsi_cookie_names())


class CsrfMiddleware(_CsrfMiddleware):
    def __init__(self, app, config: CsrfConfig | None = None) -> None:
        super().__init__(app, config=config or _DEFAULT_CONFIG)


__all__ = [
    "CSRF_COOKIE",
    "CSRF_HEADER",
    "CsrfConfig",
    "CsrfMiddleware",
    "issue_csrf_token",
    "set_csrf_cookie",
]
