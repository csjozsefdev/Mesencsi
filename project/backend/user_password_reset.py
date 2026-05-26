"""Shop user password reset tokens — hashed, expiring, single-use."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db_models import AppUser

RESET_TOKEN_TTL_MINUTES = 60


def issue_reset_token() -> str:
    """URL-safe one-time token (plain text sent by email; only hash stored)."""
    return secrets.token_urlsafe(32)


def hash_reset_token(plain: str) -> str:
    return hashlib.sha256(plain.strip().encode("utf-8")).hexdigest()


def assign_reset_to_user(db: Session, user: AppUser, plain_token: str) -> None:
    user.password_reset_token_hash = hash_reset_token(plain_token)
    user.password_reset_sent_at = datetime.now(UTC)
    user.password_reset_used_at = None


def clear_reset_on_user(user: AppUser) -> None:
    user.password_reset_token_hash = None
    user.password_reset_sent_at = None
    user.password_reset_used_at = None


def _sent_at_aware(sent: datetime) -> datetime:
    return sent if sent.tzinfo else sent.replace(tzinfo=UTC)


def reset_token_invalid_reason(user: AppUser, *, now: datetime | None = None) -> str | None:
    """
    Return None if token row is valid for reset; otherwise a short reason code:
    invalid | used | expired.
    """
    if not user.password_reset_token_hash or user.password_reset_sent_at is None:
        return "invalid"
    if user.password_reset_used_at is not None:
        return "used"
    t = now or datetime.now(UTC)
    sent = _sent_at_aware(user.password_reset_sent_at)
    if t - sent > timedelta(minutes=RESET_TOKEN_TTL_MINUTES):
        return "expired"
    return None


def find_user_for_reset_token(db: Session, plain_token: str) -> AppUser | None:
    if not plain_token or len(plain_token.strip()) < 16:
        return None
    token_hash = hash_reset_token(plain_token)
    row = db.scalar(select(AppUser).where(AppUser.password_reset_token_hash == token_hash))
    if row is None:
        return None
    if row.is_deleted or not row.is_active or row.is_banned:
        return None
    return row


def find_active_shop_user_by_email(db: Session, email: str) -> AppUser | None:
    """Shop AppUser only — admin OWNER/MAINTENANCE are env-based, not in users table."""
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        return None
    row = db.scalar(select(AppUser).where(func.lower(AppUser.email) == normalized))
    if row is None or row.is_deleted or not row.is_active or row.is_banned:
        return None
    return row
