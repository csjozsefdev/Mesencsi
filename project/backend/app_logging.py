"""Egyszerű, biztonságos naplózási segédek (nem enterprise — request_id + eseménynév)."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

request_id_cv: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_cv.get()

# Kulcsok, amelyek soha ne kerüljenek log üzenetbe / extra dict-be.
_REDACT_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "access_token",
        "authorization",
        "smtp_password",
        "secret",
        "api_key",
    }
)


def safe_log_extra(**kwargs: Any) -> dict[str, Any]:
    """Szűrt extra mezők structlog-szerű üzenetekhez (értékek rövidítve)."""
    out: dict[str, Any] = {}
    for k, v in kwargs.items():
        lk = k.lower()
        if lk in _REDACT_KEYS or "password" in lk or "token" in lk or "secret" in lk:
            out[k] = "[REDACTED]"
        elif isinstance(v, str) and len(v) > 200:
            out[k] = v[:200] + "…"
        else:
            out[k] = v
    return out


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    request_id: str | None = None,
    **fields: Any,
) -> None:
    """Egy sor: esemény + request_id + nem érzékeny mezők."""
    extra = safe_log_extra(**fields)
    parts = [f"event={event}"]
    if request_id:
        parts.append(f"request_id={request_id}")
    for k, v in extra.items():
        parts.append(f"{k}={v!r}")
    logger.log(level, " | ".join(parts))
