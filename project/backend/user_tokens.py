"""Shop user JWT — delegates to grafi_core with Mesencsi settings."""

from __future__ import annotations

import os

from mesencsi_settings import mesencsi_core_settings, mesencsi_shop_jwt_settings
from grafi_core.auth.user_jwt import (
    issue_user_access_token as _issue_user_access_token,
    log_user_jwt_startup as _log_user_jwt_startup,
    parse_user_access_token as _parse_user_access_token,
)

USER_JWT_ALG = (os.getenv("JWT_ALGORITHM") or "HS256").strip() or "HS256"


def log_user_jwt_startup() -> None:
    _log_user_jwt_startup(
        core_settings=mesencsi_core_settings(),
        jwt_settings=mesencsi_shop_jwt_settings(),
    )


def issue_user_access_token(user_id: int) -> str:
    return _issue_user_access_token(
        user_id,
        core_settings=mesencsi_core_settings(),
        jwt_settings=mesencsi_shop_jwt_settings(),
    )


def parse_user_access_token(token: str) -> int:
    return _parse_user_access_token(
        token,
        core_settings=mesencsi_core_settings(),
        jwt_settings=mesencsi_shop_jwt_settings(),
    )
