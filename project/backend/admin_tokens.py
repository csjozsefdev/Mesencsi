"""Admin JWT — delegates to grafi_core with Mesencsi settings."""

from __future__ import annotations

import os

from auth import AdminRole
from adapters.grafi_settings import mesencsi_admin_jwt_settings, mesencsi_core_settings
from grafi_core.auth.admin_jwt import (
    issue_admin_access_token as _issue_admin_access_token,
    log_admin_jwt_startup as _log_admin_jwt_startup,
    parse_admin_access_token as _parse_admin_access_token,
)

ADMIN_JWT_ALG = (os.getenv("ADMIN_JWT_ALGORITHM") or os.getenv("JWT_ALGORITHM") or "HS256").strip() or "HS256"


def log_admin_jwt_startup() -> None:
    _log_admin_jwt_startup(
        core_settings=mesencsi_core_settings(),
        jwt_settings=mesencsi_admin_jwt_settings(),
    )


def issue_admin_access_token(*, username: str, role: AdminRole) -> str:
    return _issue_admin_access_token(
        username=username,
        role=role,
        core_settings=mesencsi_core_settings(),
        jwt_settings=mesencsi_admin_jwt_settings(),
    )


def parse_admin_access_token(token: str) -> tuple[str, AdminRole]:
    return _parse_admin_access_token(
        token,
        core_settings=mesencsi_core_settings(),
        jwt_settings=mesencsi_admin_jwt_settings(),
    )
