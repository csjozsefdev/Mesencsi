"""Structured stdout logging helpers (request_id + event name)."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

request_id_cv: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_cv.get()


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
    """Filtered extra fields for structured log messages (values truncated/redacted)."""
    out: dict[str, Any] = {}
    for key, value in kwargs.items():
        lower_key = key.lower()
        if lower_key in _REDACT_KEYS or "password" in lower_key or "token" in lower_key or "secret" in lower_key:
            out[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 200:
            out[key] = value[:200] + "…"
        else:
            out[key] = value
    return out


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    request_id: str | None = None,
    **fields: Any,
) -> None:
    """Single-line log: event + request_id + non-sensitive fields."""
    extra = safe_log_extra(**fields)
    parts = [f"event={event}"]
    if request_id:
        parts.append(f"request_id={request_id}")
    for key, value in extra.items():
        parts.append(f"{key}={value!r}")
    logger.log(level, " | ".join(parts))
