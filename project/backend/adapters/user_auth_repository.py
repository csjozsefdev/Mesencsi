"""AppUser-backed auth repository and shop user lookups."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db_models import AppUser
from shop_email import normalize_shop_email


def find_by_email(db: Session, email: str) -> AppUser | None:
    normalized = normalize_shop_email(email)
    if not normalized:
        return None
    return db.scalar(select(AppUser).where(func.lower(AppUser.email) == normalized))


def find_by_id(db: Session, user_id: int) -> AppUser | None:
    return db.get(AppUser, user_id)


def find_active_shop_user_by_email(db: Session, email: str) -> AppUser | None:
    """Shop AppUser only — admin OWNER/MAINTENANCE are env-based, not in users table."""
    row = find_by_email(db, email)
    if row is None or row.is_deleted or not row.is_active or row.is_banned:
        return None
    return row


class MesencsiUserAuthRepository:
    """Session-scoped ``UserAuthRepository`` for Mesencsi ``AppUser`` rows."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def find_by_email(self, email: str) -> AppUser | None:
        return find_by_email(self._db, email)

    def find_by_id(self, user_id: int) -> AppUser | None:
        return find_by_id(self._db, user_id)
