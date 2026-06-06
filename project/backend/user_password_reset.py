"""Password reset tokens — delegates crypto/TTL to grafi_core; ORM lookups via adapter."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from adapters.user_auth_repository import find_active_shop_user_by_email
from db_models import AppUser
from grafi_core.auth.password_reset import (
    DEFAULT_RESET_TOKEN_TTL_MINUTES,
    hash_reset_token,
    issue_reset_token,
    reset_token_invalid_reason as _reset_token_invalid_reason,
    reset_token_is_valid_format,
)

RESET_TOKEN_TTL_MINUTES = DEFAULT_RESET_TOKEN_TTL_MINUTES


def assign_reset_to_user(db: Session, user: AppUser, plain_token: str) -> None:
    user.password_reset_token_hash = hash_reset_token(plain_token)
    user.password_reset_sent_at = datetime.now(UTC)
    user.password_reset_used_at = None


def clear_reset_on_user(user: AppUser) -> None:
    user.password_reset_token_hash = None
    user.password_reset_sent_at = None
    user.password_reset_used_at = None


def reset_token_invalid_reason(user: AppUser, *, now: datetime | None = None) -> str | None:
    return _reset_token_invalid_reason(
        token_hash=user.password_reset_token_hash,
        sent_at=user.password_reset_sent_at,
        used_at=user.password_reset_used_at,
        ttl_minutes=RESET_TOKEN_TTL_MINUTES,
        now=now,
    )


def find_user_for_reset_token(db: Session, plain_token: str) -> AppUser | None:
    if not reset_token_is_valid_format(plain_token):
        return None
    token_hash = hash_reset_token(plain_token)
    row = db.scalar(select(AppUser).where(AppUser.password_reset_token_hash == token_hash))
    if row is None or row.is_deleted or not row.is_active or row.is_banned:
        return None
    return row
