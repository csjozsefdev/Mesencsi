"""Email verification token helpers (no ORM coupling)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

DEFAULT_VERIFICATION_TOKEN_TTL_HOURS = 48
DEFAULT_RESEND_COOLDOWN_SEC = 120
MIN_VERIFICATION_TOKEN_LENGTH = 16


def issue_verification_token() -> str:
    return secrets.token_urlsafe(32)


def verification_token_is_valid_format(token: str) -> bool:
    return bool(token and len(token.strip()) >= MIN_VERIFICATION_TOKEN_LENGTH)


def is_verification_token_expired(
    sent_at: datetime | None,
    *,
    ttl_hours: int = DEFAULT_VERIFICATION_TOKEN_TTL_HOURS,
    now: datetime | None = None,
) -> bool:
    if sent_at is None:
        return False
    current = now or datetime.now(UTC)
    sent_aware = sent_at if sent_at.tzinfo else sent_at.replace(tzinfo=UTC)
    return current - sent_aware > timedelta(hours=ttl_hours)


def can_resend_verification(
    sent_at: datetime | None,
    *,
    cooldown_sec: int = DEFAULT_RESEND_COOLDOWN_SEC,
    now: datetime | None = None,
) -> tuple[bool, int]:
    """Return (allowed, seconds_left)."""
    current = now or datetime.now(UTC)
    if sent_at is None:
        return True, 0
    sent_aware = sent_at if sent_at.tzinfo else sent_at.replace(tzinfo=UTC)
    elapsed = (current - sent_aware).total_seconds()
    if elapsed >= cooldown_sec:
        return True, 0
    return False, int(cooldown_sec - elapsed + 0.999)
