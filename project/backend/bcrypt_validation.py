"""bcrypt hash structure validation for env / startup checks."""

from __future__ import annotations

import re

import bcrypt

_BCRYPT_HASH_RE = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")


def is_valid_bcrypt_hash(value: str) -> bool:
    """Return True when ``value`` is a syntactically valid bcrypt hash."""
    raw = (value or "").strip()
    if not raw or not _BCRYPT_HASH_RE.match(raw):
        return False
    try:
        bcrypt.hashpw(b"bcrypt-structure-check", raw.encode("ascii"))
    except (ValueError, TypeError):
        return False
    return True
