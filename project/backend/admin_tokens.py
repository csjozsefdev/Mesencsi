"""Admin JWT — külön titok és ``typ=admin``; nem keverendő a shop ``USER_JWT_SECRET``-tel."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from auth import AdminRole

_log = logging.getLogger("mesencsi.admin_jwt")

ADMIN_JWT_ALG = (os.getenv("ADMIN_JWT_ALGORITHM") or os.getenv("JWT_ALGORITHM") or "HS256").strip() or "HS256"
_ADMIN_TYP = "admin"


def _admin_token_timedelta() -> timedelta:
    hours_raw = (os.getenv("ADMIN_JWT_EXPIRE_HOURS") or "").strip()
    if hours_raw.replace(".", "", 1).isdigit() and float(hours_raw) > 0:
        return timedelta(hours=float(hours_raw))
    minutes_raw = (os.getenv("ADMIN_JWT_EXPIRE_MINUTES") or "").strip()
    if minutes_raw.isdigit() and int(minutes_raw) > 0:
        return timedelta(minutes=int(minutes_raw))
    return timedelta(hours=12)


def log_admin_jwt_startup() -> None:
    s = (os.getenv("ADMIN_JWT_SECRET") or "").strip()
    if s:
        _log.info("Admin JWT secret loaded (ADMIN_JWT_SECRET set, length=%s)", len(s))
    else:
        _log.warning(
            "ADMIN_JWT_SECRET missing — set in .env; POST /admin/login cannot issue tokens until then."
        )


def _admin_jwt_secret() -> str:
    s = (os.getenv("ADMIN_JWT_SECRET") or "").strip()
    if not s:
        _log.error("ADMIN_JWT_SECRET missing — cannot sign admin token")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A szerver ADMIN_JWT_SECRET kulcs nélkül nem adhat ki admin belépési tokent.",
        )
    return s


def issue_admin_access_token(*, username: str, role: AdminRole) -> str:
    secret = _admin_jwt_secret()
    now = datetime.now(timezone.utc)
    delta = _admin_token_timedelta()
    payload = {
        "sub": username.strip(),
        "role": role,
        "typ": _ADMIN_TYP,
        "iat": int(now.timestamp()),
        "exp": int((now + delta).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ADMIN_JWT_ALG)


def parse_admin_access_token(token: str) -> tuple[str, AdminRole]:
    secret = _admin_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[ADMIN_JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Az admin belépési azonosító lejárt. Jelentkezz be újra.",
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen admin belépési azonosító.",
        ) from None
    if payload.get("typ") != _ADMIN_TYP:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen admin belépési azonosító.",
        )
    username = str(payload.get("sub") or "").strip()
    role_part = str(payload.get("role") or "").strip()
    if not username or role_part not in ("maintenance", "owner"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen admin belépési azonosító.",
        )
    return username, role_part  # type: ignore[return-value]
