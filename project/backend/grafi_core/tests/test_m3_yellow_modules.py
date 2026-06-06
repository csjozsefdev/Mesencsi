"""Tests for grafi_core YELLOW auth/ops modules (Milestone 3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from grafi_core.auth.email_verify import (
    can_resend_verification,
    is_verification_token_expired,
    issue_verification_token,
    verification_token_is_valid_format,
)
from grafi_core.auth.login_throttle import (
    LoginThrottleSettings,
    assert_login_allowed,
    clear_login_throttle,
    record_login_failure,
)
from grafi_core.auth.password_reset import (
    hash_reset_token,
    issue_reset_token,
    reset_token_invalid_reason,
    reset_token_is_valid_format,
)
from grafi_core.ops.startup_helpers import (
    StartupConfigError,
    https_public_url,
    secret_ok,
)


class InMemoryThrottleStore:
    def __init__(self) -> None:
        self.locked_until: dict[str, datetime | None] = {}
        self.failed_count: dict[str, int] = {}

    def get_locked_until(self, db, email_key: str) -> datetime | None:
        return self.locked_until.get(email_key)

    def get_failed_count(self, db, email_key: str) -> int:
        return self.failed_count.get(email_key, 0)

    def save_failure(
        self,
        db,
        email_key: str,
        *,
        failed_count: int,
        locked_until: datetime | None,
        updated_at: datetime,
    ) -> None:
        self.failed_count[email_key] = failed_count
        self.locked_until[email_key] = locked_until

    def clear(self, db, email_key: str) -> None:
        self.failed_count.pop(email_key, None)
        self.locked_until.pop(email_key, None)


def test_issue_verification_token_length_and_format() -> None:
    token = issue_verification_token()
    assert verification_token_is_valid_format(token)
    assert not verification_token_is_valid_format("short")


def test_verification_token_expiry() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    sent = now - timedelta(hours=49)
    assert is_verification_token_expired(sent, now=now) is True
    assert is_verification_token_expired(now - timedelta(hours=1), now=now) is False
    assert is_verification_token_expired(None, now=now) is False


def test_can_resend_verification_cooldown() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    sent = now - timedelta(seconds=30)
    ok, wait = can_resend_verification(sent, cooldown_sec=120, now=now)
    assert ok is False
    assert wait > 0
    ok2, wait2 = can_resend_verification(None, now=now)
    assert ok2 is True
    assert wait2 == 0


def test_reset_token_hash_and_validation() -> None:
    plain = issue_reset_token()
    assert reset_token_is_valid_format(plain)
    assert not reset_token_is_valid_format("x")
    hashed = hash_reset_token(plain)
    assert len(hashed) == 64
    assert hash_reset_token(plain) == hashed


def test_reset_token_invalid_reason_states() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    sent = now - timedelta(minutes=5)
    assert reset_token_invalid_reason(token_hash=None, sent_at=sent, used_at=None, now=now) == "invalid"
    assert (
        reset_token_invalid_reason(
            token_hash=hash_reset_token("token"),
            sent_at=sent,
            used_at=now,
            now=now,
        )
        == "used"
    )
    old_sent = now - timedelta(minutes=90)
    assert (
        reset_token_invalid_reason(
            token_hash=hash_reset_token("token"),
            sent_at=old_sent,
            used_at=None,
            now=now,
        )
        == "expired"
    )
    assert (
        reset_token_invalid_reason(
            token_hash=hash_reset_token("token"),
            sent_at=sent,
            used_at=None,
            now=now,
        )
        is None
    )


def test_login_throttle_locks_after_max_fails() -> None:
    store = InMemoryThrottleStore()
    db = MagicMock()
    settings = LoginThrottleSettings(max_fails=3, lock_minutes=10)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    for _ in range(3):
        record_login_failure(db, "User@Example.com", store, settings=settings, now=now)
    with pytest.raises(HTTPException) as exc:
        assert_login_allowed(db, "user@example.com", store, settings=settings, now=now)
    assert exc.value.status_code == 429
    clear_login_throttle(db, "user@example.com", store)
    assert_login_allowed(db, "user@example.com", store, settings=settings, now=now)


def test_startup_helpers_secret_and_https() -> None:
    ok, err = secret_ok("TEST_SECRET", min_len=8)
    assert ok is False
    assert err is not None

    ok2, err2 = https_public_url("PUBLIC", "http://example.com")
    assert ok2 is False
    assert "https" in (err2 or "")

    ok3, _ = https_public_url("PUBLIC", "https://shop.example.com")
    assert ok3 is True


def test_startup_config_error_message() -> None:
    err = StartupConfigError(["missing JWT", "bad CORS"])
    assert "missing JWT" in str(err)
    assert err.issues == ["missing JWT", "bad CORS"]
