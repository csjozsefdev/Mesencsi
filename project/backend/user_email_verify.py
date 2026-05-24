"""E-mail megerősítés token generálás / ellenőrzés."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from db_models import AppUser
from email_outbound import RESEND_COOLDOWN_SEC

TOKEN_TTL_HOURS = 48


def issue_verification_token() -> str:
    return secrets.token_urlsafe(32)


def assign_verification_to_user(db: Session, user: AppUser, token: str) -> None:
    user.email_verification_token = token
    user.email_verification_sent_at = datetime.now(UTC)
    user.email_verified_at = None


def verify_user_by_token(db: Session, token: str) -> AppUser | None:
    if not token or len(token) < 16:
        return None
    row = db.scalar(select(AppUser).where(AppUser.email_verification_token == token.strip()))
    if row is None:
        return None
    if row.is_deleted:
        return None
    sent = row.email_verification_sent_at
    if sent is not None:
        sent_aware = sent if sent.tzinfo else sent.replace(tzinfo=UTC)
        if datetime.now(UTC) - sent_aware > timedelta(hours=TOKEN_TTL_HOURS):
            return None
    row.email_verified_at = datetime.now(UTC)
    row.email_verification_token = None
    row.email_verification_sent_at = None
    db.commit()
    db.refresh(row)
    return row


def can_resend_verification(user: AppUser, *, now: datetime | None = None) -> tuple[bool, int]:
    """(allowed, seconds_left)."""
    t = now or datetime.now(UTC)
    sent = user.email_verification_sent_at
    if sent is None:
        return True, 0
    sent_aware = sent if sent.tzinfo else sent.replace(tzinfo=UTC)
    elapsed = (t - sent_aware).total_seconds()
    if elapsed >= RESEND_COOLDOWN_SEC:
        return True, 0
    return False, int(RESEND_COOLDOWN_SEC - elapsed + 0.999)
