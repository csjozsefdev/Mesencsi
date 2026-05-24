"""Vásárlói (shop user) JWT — elkülönül az admin JWT-től (``ADMIN_JWT_SECRET``, ``typ=admin``)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

_log = logging.getLogger("mesencsi.user_jwt")

USER_JWT_ALG = (os.getenv("JWT_ALGORITHM") or "HS256").strip() or "HS256"


def _access_token_timedelta() -> timedelta:
    raw = (os.getenv("JWT_EXPIRE_MINUTES") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return timedelta(minutes=int(raw))
    days_raw = (os.getenv("USER_JWT_EXPIRE_DAYS") or "7").strip()
    try:
        days = int(days_raw)
    except ValueError:
        days = 7
    return timedelta(days=max(1, days))


def log_user_jwt_startup() -> None:
    """Indításkor: USER_JWT_SECRET állapot (login előtt is látszódjon a naplóban)."""
    s = (os.getenv("USER_JWT_SECRET") or "").strip()
    if s:
        _log.info("JWT secret loaded (USER_JWT_SECRET set, length=%s)", len(s))
    else:
        _log.warning("JWT secret missing — set USER_JWT_SECRET in .env; shop /auth/login will fail until then")


def _user_jwt_secret() -> str:
    s = (os.getenv("USER_JWT_SECRET") or "").strip()
    if not s:
        _log.error("JWT secret missing — cannot sign shop user token")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A szerver USER_JWT_SECRET kulcs nélkül nem adhat ki belépési tokent. Állítsd be a .env fájlban.",
        )
    return s


def issue_user_access_token(user_id: int) -> str:
    secret = _user_jwt_secret()
    _log.info("Generating login token for user_id=%s", user_id)
    now = datetime.now(timezone.utc)
    delta = _access_token_timedelta()
    payload = {
        "sub": str(user_id),
        "typ": "user",
        "iat": int(now.timestamp()),
        "exp": int((now + delta).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=USER_JWT_ALG)


def parse_user_access_token(token: str) -> int:
    secret = _user_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[USER_JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A belépési azonosító lejárt. Jelentkezz be újra.",
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen belépési azonosító.",
        ) from None
    if payload.get("typ") != "user":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen belépési azonosító.",
        )
    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen belépési azonosító.",
        ) from None
