"""HTTP security headers — delegates to grafi_core with Mesencsi production flag."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grafi_core.security.headers import SECURITY_HEADER_VALUES
from grafi_core.security.headers import SecurityHeadersMiddleware as _SecurityHeadersMiddleware
from grafi_core.security.headers import apply_security_headers as _apply_security_headers
from grafi_core.security.headers import register_security_headers as _register_security_headers
from runtime_flags import mesencsi_production
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from fastapi import FastAPI


def apply_security_headers(response: Response) -> None:
    _apply_security_headers(response, is_production=mesencsi_production)


class SecurityHeadersMiddleware(_SecurityHeadersMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app, is_production=mesencsi_production)


def register_security_headers(app: FastAPI) -> None:
    _register_security_headers(app, is_production=mesencsi_production)


__all__ = [
    "SECURITY_HEADER_VALUES",
    "SecurityHeadersMiddleware",
    "apply_security_headers",
    "register_security_headers",
]
