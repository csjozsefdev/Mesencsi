"""Sikertelen belépés számolása + ideiglenes zárolás."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from db_models import LoginThrottle

MAX_FAILS = 5
LOCK_MINUTES = 15


def _key(email: str) -> str:
    return email.strip().lower()


def _as_utc(dt: datetime) -> datetime:
    """SQLite teszt DB naív datetimeot ad vissza — összehasonlítás előtt normalizálás."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def assert_login_allowed(db: Session, email: str) -> None:
    row = db.get(LoginThrottle, _key(email))
    if row is None or row.locked_until is None:
        return
    if _as_utc(row.locked_until) > datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Túl sok sikertelen belépési kísérlet. Próbáld újra később (kb. 15 perc múlva).",
        )


def record_login_failure(db: Session, email: str) -> None:
    key = _key(email)
    row = db.get(LoginThrottle, key)
    now = datetime.now(UTC)
    if row is None:
        row = LoginThrottle(email_normalized=key, failed_count=1, locked_until=None, updated_at=now)
        db.add(row)
    else:
        row.failed_count = int(row.failed_count or 0) + 1
        row.updated_at = now
        if row.failed_count >= MAX_FAILS:
            row.locked_until = now + timedelta(minutes=LOCK_MINUTES)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def clear_login_throttle(db: Session, email: str) -> None:
    key = _key(email)
    row = db.get(LoginThrottle, key)
    if row is None:
        return
    db.delete(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
