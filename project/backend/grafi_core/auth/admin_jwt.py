"""Admin JWT issue and parse — separate secret and typ from shop user tokens."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import HTTPException, status

from grafi_core.settings.core_settings import CoreSettings
from grafi_core.settings.jwt_settings import AdminJwtErrorMessages, AdminJwtSettings

AdminRole = Literal["owner", "maintenance"]

_DEFAULT_SETTINGS = AdminJwtSettings()
_DEFAULT_ERRORS = AdminJwtErrorMessages()


def _logger(settings: CoreSettings) -> logging.Logger:
    return logging.getLogger(f"{settings.logger_prefix}.admin_jwt")


def _algorithm(jwt_settings: AdminJwtSettings) -> str:
    raw = (
        os.getenv(jwt_settings.algorithm_env_key)
        or os.getenv(jwt_settings.fallback_algorithm_env_key)
        or jwt_settings.default_algorithm
    ).strip()
    return raw or jwt_settings.default_algorithm


def _admin_token_timedelta(jwt_settings: AdminJwtSettings) -> timedelta:
    hours_raw = (os.getenv(jwt_settings.expire_hours_env_key) or "").strip()
    if hours_raw.replace(".", "", 1).isdigit() and float(hours_raw) > 0:
        return timedelta(hours=float(hours_raw))
    minutes_raw = (os.getenv(jwt_settings.expire_minutes_env_key) or "").strip()
    if minutes_raw.isdigit() and int(minutes_raw) > 0:
        return timedelta(minutes=int(minutes_raw))
    return timedelta(hours=jwt_settings.default_expire_hours)


def log_admin_jwt_startup(
    *,
    core_settings: CoreSettings | None = None,
    jwt_settings: AdminJwtSettings | None = None,
) -> None:
    core = core_settings or CoreSettings.from_env()
    js = jwt_settings or _DEFAULT_SETTINGS
    log = _logger(core)
    secret = (os.getenv(js.secret_env_key) or "").strip()
    if secret:
        log.info("Admin JWT secret loaded (%s set, length=%s)", js.secret_env_key, len(secret))
    else:
        log.warning(
            "Admin JWT secret missing — set %s in .env; admin login cannot issue tokens until then.",
            js.secret_env_key,
        )


def _errors(jwt_settings: AdminJwtSettings) -> AdminJwtErrorMessages:
    return jwt_settings.error_messages or _DEFAULT_ERRORS


def _admin_jwt_secret(jwt_settings: AdminJwtSettings, core_settings: CoreSettings) -> str:
    secret = (os.getenv(jwt_settings.secret_env_key) or "").strip()
    if not secret:
        _logger(core_settings).error(
            "Admin JWT secret missing — cannot sign admin token (%s)",
            jwt_settings.secret_env_key,
        )
        errors = _errors(jwt_settings)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=errors.missing_secret.format(secret_env_key=jwt_settings.secret_env_key),
        )
    return secret


def issue_admin_access_token(
    *,
    username: str,
    role: AdminRole,
    core_settings: CoreSettings | None = None,
    jwt_settings: AdminJwtSettings | None = None,
) -> str:
    core = core_settings or CoreSettings.from_env()
    js = jwt_settings or _DEFAULT_SETTINGS
    secret = _admin_jwt_secret(js, core)
    now = datetime.now(timezone.utc)
    delta = _admin_token_timedelta(js)
    payload = {
        "sub": username.strip(),
        "role": role,
        "typ": js.typ,
        "iat": int(now.timestamp()),
        "exp": int((now + delta).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_algorithm(js))


def parse_admin_access_token(
    token: str,
    *,
    core_settings: CoreSettings | None = None,
    jwt_settings: AdminJwtSettings | None = None,
) -> tuple[str, AdminRole]:
    core = core_settings or CoreSettings.from_env()
    js = jwt_settings or _DEFAULT_SETTINGS
    errors = _errors(js)
    secret = _admin_jwt_secret(js, core)
    alg = _algorithm(js)
    try:
        payload = jwt.decode(token, secret, algorithms=[alg])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=errors.expired,
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=errors.invalid,
        ) from None
    if payload.get("typ") != js.typ:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=errors.invalid,
        )
    username = str(payload.get("sub") or "").strip()
    role_part = str(payload.get("role") or "").strip()
    if not username or role_part not in js.allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=errors.invalid,
        )
    return username, role_part  # type: ignore[return-value]
