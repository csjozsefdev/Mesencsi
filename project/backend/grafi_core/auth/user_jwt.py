"""Shop user JWT issue and parse — separate from admin JWT domain."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from grafi_core.settings.core_settings import CoreSettings
from grafi_core.settings.jwt_settings import ShopJwtErrorMessages, ShopJwtSettings

_DEFAULT_SETTINGS = ShopJwtSettings()
_DEFAULT_ERRORS = ShopJwtErrorMessages()


def _logger(settings: CoreSettings) -> logging.Logger:
    return logging.getLogger(f"{settings.logger_prefix}.user_jwt")


def _algorithm(jwt_settings: ShopJwtSettings) -> str:
    raw = (os.getenv(jwt_settings.algorithm_env_key) or jwt_settings.default_algorithm).strip()
    return raw or jwt_settings.default_algorithm


def _access_token_timedelta(jwt_settings: ShopJwtSettings) -> timedelta:
    raw = (os.getenv(jwt_settings.expire_minutes_env_key) or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return timedelta(minutes=int(raw))
    days_raw = (os.getenv(jwt_settings.expire_days_env_key) or str(jwt_settings.default_expire_days)).strip()
    try:
        days = int(days_raw)
    except ValueError:
        days = jwt_settings.default_expire_days
    return timedelta(days=max(1, days))


def log_user_jwt_startup(
    *,
    core_settings: CoreSettings | None = None,
    jwt_settings: ShopJwtSettings | None = None,
) -> None:
    core = core_settings or CoreSettings.from_env()
    js = jwt_settings or _DEFAULT_SETTINGS
    log = _logger(core)
    secret = (os.getenv(js.secret_env_key) or "").strip()
    if secret:
        log.info("JWT secret loaded (%s set, length=%s)", js.secret_env_key, len(secret))
    else:
        log.warning(
            "JWT secret missing — set %s in .env; shop login will fail until then",
            js.secret_env_key,
        )


def _errors(jwt_settings: ShopJwtSettings) -> ShopJwtErrorMessages:
    return jwt_settings.error_messages or _DEFAULT_ERRORS


def _user_jwt_secret(
    jwt_settings: ShopJwtSettings,
    core_settings: CoreSettings,
) -> str:
    secret = (os.getenv(jwt_settings.secret_env_key) or "").strip()
    if not secret:
        _logger(core_settings).error(
            "JWT secret missing — cannot sign shop user token (%s)",
            jwt_settings.secret_env_key,
        )
        errors = _errors(jwt_settings)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=errors.missing_secret.format(secret_env_key=jwt_settings.secret_env_key),
        )
    return secret


def issue_user_access_token(
    user_id: int,
    *,
    core_settings: CoreSettings | None = None,
    jwt_settings: ShopJwtSettings | None = None,
) -> str:
    core = core_settings or CoreSettings.from_env()
    js = jwt_settings or _DEFAULT_SETTINGS
    secret = _user_jwt_secret(js, core)
    _logger(core).info("Generating login token for user_id=%s", user_id)
    now = datetime.now(timezone.utc)
    delta = _access_token_timedelta(js)
    payload = {
        "sub": str(user_id),
        "typ": js.typ,
        "iat": int(now.timestamp()),
        "exp": int((now + delta).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_algorithm(js))


def parse_user_access_token(
    token: str,
    *,
    core_settings: CoreSettings | None = None,
    jwt_settings: ShopJwtSettings | None = None,
) -> int:
    core = core_settings or CoreSettings.from_env()
    js = jwt_settings or _DEFAULT_SETTINGS
    errors = _errors(js)
    secret = _user_jwt_secret(js, core)
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
    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=errors.invalid,
        ) from None
