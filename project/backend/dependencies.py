from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from auth import AdminRole, decode_admin_token
from database import get_db
from db_models import AppUser
from user_tokens import parse_user_access_token


@dataclass(frozen=True)
class CurrentAdmin:
    username: str
    role: AdminRole


_ADMIN_COOKIE = "mesencsi_admin_token"
_USER_COOKIE = "mesencsi_user_token"


def get_current_admin(
    authorization: str | None = Header(default=None),
    admin_cookie: str | None = Cookie(default=None, alias=_ADMIN_COOKIE),
) -> CurrentAdmin:
    """Admin auth via Bearer header or HttpOnly cookie (preferred)."""
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif admin_cookie:
        token = str(admin_cookie).strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Hiányzik a belépési azonosító.")
    if "|" in token and token.count(".") != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Elavult admin azonosító. Jelentkezz be újra az /admin/login oldalon.",
        )
    username, role = decode_admin_token(token)
    return CurrentAdmin(username=username, role=role)


def require_role(roles: list[AdminRole]) -> Callable[..., CurrentAdmin]:
    """Depends on ``get_current_admin``; returns 403 if ``admin.role`` not in ``roles``."""

    def _checker(admin: CurrentAdmin = Depends(get_current_admin)) -> CurrentAdmin:
        if admin.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nincs jogosultságod ehhez a művelethez.")
        return admin

    return _checker


http_bearer_user = HTTPBearer(auto_error=False)


def get_current_app_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer_user),
    db: Session = Depends(get_db),
    user_cookie: str | None = Cookie(default=None, alias=_USER_COOKIE),
) -> AppUser:
    """Shop user auth via Bearer header or HttpOnly cookie (preferred)."""
    token = ""
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials.strip()
    elif user_cookie:
        token = str(user_cookie).strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Hiányzik a belépési token.")
    if token.count(".") != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen vásárlói token. Az admin belépéshez az /admin/login és a megfelelő token szükséges.",
        )
    user_id, token_version = parse_user_access_token(token)
    row = db.get(AppUser, user_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A felhasználó nem található.")
    if int(row.token_version or 0) != int(token_version):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A belépési azonosító érvénytelen. Jelentkezz be újra.",
        )
    if row.is_deleted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ez a fiók nem elérhető.")
    if row.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ez a fiók tiltva van.")
    if not row.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ez a fiók inaktív.")
    return row


def require_email_verified_shop_user(user: AppUser = Depends(get_current_app_user)) -> AppUser:
    """Rendeléskövetés és egyes shop funkciók csak megerősített e-mail után."""
    if user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ehhez erősítsd meg az e-mail címed (a regisztrációkor küldött linkkel).",
        )
    return user


def require_email_verified_to_place_order(user: AppUser = Depends(get_current_app_user)) -> AppUser:
    """Checkout: rendelés létrehozása csak megerősített e-mail után (összhangban a GET /orders listával)."""
    if user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A rendelés leadásához erősítsd meg az e-mail címed.",
        )
    return user


def get_optional_app_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer_user),
    db: Session = Depends(get_db),
    user_cookie: str | None = Cookie(default=None, alias=_USER_COOKIE),
) -> AppUser | None:
    """Optional shop user — returns None when no valid session (guest checkout)."""
    try:
        return get_current_app_user(credentials=credentials, db=db, user_cookie=user_cookie)
    except HTTPException:
        return None

