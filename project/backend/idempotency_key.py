"""Idempotency-Key header validation for POST /orders."""

from __future__ import annotations

import re

_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")
_MAX_LEN = 128
_MIN_LEN = 8


class IdempotencyKeyError(ValueError):
    """Client supplied an invalid idempotency key."""


def parse_idempotency_key_header(raw: str | None) -> str | None:
    """
    Normalize a header value or return None when absent/blank.
    Raises IdempotencyKeyError for malformed keys.
    """
    if raw is None:
        return None
    key = str(raw).strip()
    if not key:
        return None
    if len(key) > _MAX_LEN:
        raise IdempotencyKeyError(
            f"Az Idempotency-Key legfeljebb {_MAX_LEN} karakter lehet."
        )
    if len(key) < _MIN_LEN:
        raise IdempotencyKeyError(
            f"Az Idempotency-Key legalább {_MIN_LEN} karakter legyen."
        )
    if not _IDEMPOTENCY_KEY_RE.match(key):
        raise IdempotencyKeyError(
            "Az Idempotency-Key csak betűket, számokat, kötőjelet és aláhúzást tartalmazhat."
        )
    return key
