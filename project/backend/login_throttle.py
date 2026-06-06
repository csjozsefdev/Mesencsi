"""Login throttle — delegates to grafi_core with Mesencsi store and Hungarian message."""

from __future__ import annotations

from sqlalchemy.orm import Session

from adapters.login_throttle_store import MESENCI_LOGIN_THROTTLE_STORE
from grafi_core.auth.login_throttle import (
    LoginThrottleSettings,
    assert_login_allowed as _assert_login_allowed,
    clear_login_throttle as _clear_login_throttle,
    record_login_failure as _record_login_failure,
)

_SETTINGS = LoginThrottleSettings(
    max_fails=5,
    lock_minutes=15,
    locked_message="Túl sok sikertelen belépési kísérlet. Próbáld újra később (kb. 15 perc múlva).",
)

MAX_FAILS = _SETTINGS.max_fails
LOCK_MINUTES = _SETTINGS.lock_minutes


def assert_login_allowed(db: Session, email: str) -> None:
    _assert_login_allowed(db, email, MESENCI_LOGIN_THROTTLE_STORE, settings=_SETTINGS)


def record_login_failure(db: Session, email: str) -> None:
    _record_login_failure(db, email, MESENCI_LOGIN_THROTTLE_STORE, settings=_SETTINGS)


def clear_login_throttle(db: Session, email: str) -> None:
    _clear_login_throttle(db, email, MESENCI_LOGIN_THROTTLE_STORE)
