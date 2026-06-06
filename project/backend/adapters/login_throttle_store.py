"""SQLAlchemy login throttle store for Mesencsi."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from db_models import LoginThrottle
from grafi_core.auth.login_throttle import LoginThrottleStore


class SqlAlchemyLoginThrottleStore:
    def get_locked_until(self, db: Any, email_key: str) -> datetime | None:
        row = db.get(LoginThrottle, email_key)
        return None if row is None else row.locked_until

    def get_failed_count(self, db: Any, email_key: str) -> int:
        row = db.get(LoginThrottle, email_key)
        return 0 if row is None else int(row.failed_count or 0)

    def save_failure(
        self,
        db: Any,
        email_key: str,
        *,
        failed_count: int,
        locked_until: datetime | None,
        updated_at: datetime,
    ) -> None:
        row = db.get(LoginThrottle, email_key)
        if row is None:
            row = LoginThrottle(
                email_normalized=email_key,
                failed_count=failed_count,
                locked_until=locked_until,
                updated_at=updated_at,
            )
            db.add(row)
        else:
            row.failed_count = failed_count
            row.locked_until = locked_until
            row.updated_at = updated_at
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    def clear(self, db: Any, email_key: str) -> None:
        row = db.get(LoginThrottle, email_key)
        if row is None:
            return
        db.delete(row)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise


MESENCI_LOGIN_THROTTLE_STORE = SqlAlchemyLoginThrottleStore()
