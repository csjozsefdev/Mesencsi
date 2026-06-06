"""Email verification — delegates token logic to grafi_core; ORM helpers stay here."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db_models import AppUser
from grafi_core.auth.email_verify import (
    DEFAULT_RESEND_COOLDOWN_SEC,
    DEFAULT_VERIFICATION_TOKEN_TTL_HOURS,
    can_resend_verification as _can_resend_verification,
    is_verification_token_expired,
    issue_verification_token,
    verification_token_is_valid_format,
)

TOKEN_TTL_HOURS = DEFAULT_VERIFICATION_TOKEN_TTL_HOURS
RESEND_COOLDOWN_SEC = DEFAULT_RESEND_COOLDOWN_SEC


def assign_verification_to_user(db: Session, user: AppUser, token: str) -> None:
    user.email_verification_token = token
    user.email_verification_sent_at = datetime.now(UTC)
    user.email_verified_at = None


def verify_user_by_token(db: Session, token: str) -> AppUser | None:
    if not verification_token_is_valid_format(token):
        return None
    row = db.scalar(select(AppUser).where(AppUser.email_verification_token == token.strip()))
    if row is None or row.is_deleted:
        return None
    if is_verification_token_expired(row.email_verification_sent_at, ttl_hours=TOKEN_TTL_HOURS):
        return None
    row.email_verified_at = datetime.now(UTC)
    row.email_verification_token = None
    row.email_verification_sent_at = None
    db.commit()
    db.refresh(row)
    return row


def can_resend_verification(user: AppUser, *, now: datetime | None = None) -> tuple[bool, int]:
    return _can_resend_verification(
        user.email_verification_sent_at,
        cooldown_sec=RESEND_COOLDOWN_SEC,
        now=now,
    )
