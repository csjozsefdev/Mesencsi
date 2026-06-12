from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, status

from env_loader import BACKEND_DIR as _BACKEND_DIR
from bcrypt_validation import is_valid_bcrypt_hash
from password_utils import verify_password

_log = logging.getLogger("mesencsi.admin_auth")

AdminRole = Literal["maintenance", "owner"]

_ADMIN_ENV_NAMES = (
    "OWNER_USERNAME",
    "OWNER_PASSWORD",
    "MAINTENANCE_USERNAME",
    "MAINTENANCE_PASSWORD",
)


def _require_env_var(name: str) -> str:
    v = os.environ.get(name)
    if v is None or not str(v).strip():
        raise ValueError(
            f"Missing or empty {name} in environment — set it in {_BACKEND_DIR / '.env'} "
            f"(see .env.example). Admin login is disabled until all admin env vars are set."
        )
    return str(v).strip()


def _require_bcrypt_hash(name: str) -> str:
    raw = _require_env_var(name)
    if not is_valid_bcrypt_hash(raw):
        raise ValueError(
            f"{name} must be a valid bcrypt hash. "
            'Generate one with: python -c "from password_utils import hash_password; '
            "print(hash_password('YOUR_PASSWORD'))\""
        )
    return raw


@dataclass(frozen=True)
class _AdminCredentials:
    owner_username: str
    owner_password_hash: str
    maintenance_username: str
    maintenance_password_hash: str


_admin_creds: _AdminCredentials | None = None
_admin_creds_resolved = False


def _load_admin_credentials() -> _AdminCredentials | None:
    global _admin_creds, _admin_creds_resolved
    if _admin_creds_resolved:
        return _admin_creds
    _admin_creds_resolved = True
    try:
        _admin_creds = _AdminCredentials(
            owner_username=_require_env_var("OWNER_USERNAME"),
            owner_password_hash=_require_bcrypt_hash("OWNER_PASSWORD"),
            maintenance_username=_require_env_var("MAINTENANCE_USERNAME"),
            maintenance_password_hash=_require_bcrypt_hash("MAINTENANCE_PASSWORD"),
        )
    except ValueError as exc:
        _admin_creds = None
        _log.warning("%s", exc)
    return _admin_creds


def admin_auth_configured() -> bool:
    return _load_admin_credentials() is not None


def log_admin_auth_startup() -> None:
    from admin_tokens import log_admin_jwt_startup

    log_admin_jwt_startup()
    creds = _load_admin_credentials()
    if creds is not None:
        _log.info(
            "Admin auth configured (OWNER_USERNAME=%s, MAINTENANCE_USERNAME=%s)",
            creds.owner_username,
            creds.maintenance_username,
        )
    else:
        _log.warning(
            "Admin auth not configured — set %s in %s; POST /admin/login is disabled until then.",
            ", ".join(_ADMIN_ENV_NAMES),
            _BACKEND_DIR / ".env",
        )


def admin_shell_usernames() -> tuple[str, str]:
    """Configured admin login usernames (owner, then maintenance) for protected-account heuristics."""
    creds = _load_admin_credentials()
    if creds is None:
        return ("", "")
    return creds.owner_username, creds.maintenance_username


def create_admin_token(*, username: str, role: AdminRole) -> str:
    """Aláírt admin JWT (``ADMIN_JWT_SECRET``) — nem keverendő a shop user JWT-vel."""
    from admin_tokens import issue_admin_access_token

    return issue_admin_access_token(username=username, role=role)


def decode_admin_token(token: str) -> tuple[str, AdminRole]:
    from admin_tokens import parse_admin_access_token

    return parse_admin_access_token(token)


def authenticate_admin(username: str, password: str) -> tuple[str, AdminRole]:
    creds = _load_admin_credentials()
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Az admin belépés nincs konfigurálva a szerveren. Állítsd be a .env fájlban az OWNER_* és MAINTENANCE_* változókat.",
        )
    submitted = username.strip()
    if not submitted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Hibás felhasználónév vagy jelszó.")
    if submitted == creds.owner_username and verify_password(password, creds.owner_password_hash):
        return creds.owner_username, "owner"
    if submitted == creds.maintenance_username and verify_password(password, creds.maintenance_password_hash):
        return creds.maintenance_username, "maintenance"
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Hibás felhasználónév vagy jelszó.")
