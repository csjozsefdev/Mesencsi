"""Login throttle helpers and store protocol."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from fastapi import HTTPException, status


@dataclass(frozen=True)
class LoginThrottleSettings:
    max_fails: int = 5
    lock_minutes: int = 15
    locked_message: str = "Too many failed login attempts. Try again in about 15 minutes."


@runtime_checkable
class LoginThrottleStore(Protocol):
    def get_locked_until(self, db: Any, email_key: str) -> datetime | None: ...

    def get_failed_count(self, db: Any, email_key: str) -> int: ...

    def save_failure(
        self,
        db: Any,
        email_key: str,
        *,
        failed_count: int,
        locked_until: datetime | None,
        updated_at: datetime,
    ) -> None: ...

    def clear(self, db: Any, email_key: str) -> None: ...


def normalize_email_key(email: str) -> str:
    return email.strip().lower()


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def assert_login_allowed(
    db: Any,
    email: str,
    store: LoginThrottleStore,
    *,
    settings: LoginThrottleSettings | None = None,
    now: datetime | None = None,
) -> None:
    cfg = settings or LoginThrottleSettings()
    key = normalize_email_key(email)
    locked_until = store.get_locked_until(db, key)
    if locked_until is None:
        return
    current = now or datetime.now(UTC)
    if as_utc(locked_until) > current:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=cfg.locked_message,
        )


def record_login_failure(
    db: Any,
    email: str,
    store: LoginThrottleStore,
    *,
    settings: LoginThrottleSettings | None = None,
    now: datetime | None = None,
) -> None:
    cfg = settings or LoginThrottleSettings()
    key = normalize_email_key(email)
    current = now or datetime.now(UTC)
    failed_count = store.get_failed_count(db, key) + 1
    locked_until = None
    if failed_count >= cfg.max_fails:
        locked_until = current + timedelta(minutes=cfg.lock_minutes)
    store.save_failure(
        db,
        key,
        failed_count=failed_count,
        locked_until=locked_until,
        updated_at=current,
    )


def clear_login_throttle(db: Any, email: str, store: LoginThrottleStore) -> None:
    store.clear(db, normalize_email_key(email))
