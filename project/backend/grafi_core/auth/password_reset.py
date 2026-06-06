"""Password reset token helpers (no ORM coupling)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

DEFAULT_RESET_TOKEN_TTL_MINUTES = 60
MIN_RESET_TOKEN_LENGTH = 16


def issue_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(plain: str) -> str:
    return hashlib.sha256(plain.strip().encode("utf-8")).hexdigest()


def reset_token_is_valid_format(plain_token: str) -> bool:
    return bool(plain_token and len(plain_token.strip()) >= MIN_RESET_TOKEN_LENGTH)


def _sent_at_aware(sent: datetime) -> datetime:
    return sent if sent.tzinfo else sent.replace(tzinfo=UTC)


def reset_token_invalid_reason(
    *,
    token_hash: str | None,
    sent_at: datetime | None,
    used_at: datetime | None,
    ttl_minutes: int = DEFAULT_RESET_TOKEN_TTL_MINUTES,
    now: datetime | None = None,
) -> str | None:
    """
    Return None if valid for reset; otherwise invalid | used | expired.
    """
    if not token_hash or sent_at is None:
        return "invalid"
    if used_at is not None:
        return "used"
    current = now or datetime.now(UTC)
    if current - _sent_at_aware(sent_at) > timedelta(minutes=ttl_minutes):
        return "expired"
    return None
