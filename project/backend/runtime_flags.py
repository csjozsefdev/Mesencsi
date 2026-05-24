"""Éles vs fejlesztői viselkedés: ``MESENCSI_PRODUCTION``, opcionális belső debug titok."""

from __future__ import annotations

import os
from secrets import compare_digest


def mesencsi_production() -> bool:
    """``MESENCSI_PRODUCTION=true`` (vagy 1/yes/on) → éles szabályok (stub tiltás, manuális callback tiltás)."""
    v = (os.environ.get("MESENCSI_PRODUCTION") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def internal_barion_debug_authorized(x_internal_debug: str | None) -> bool:
    """
    Csak ha ``MESENCSI_INTERNAL_DEBUG_SECRET`` be van állítva a .env-ben, és a kérés
    ``X-Internal-Debug`` fejléce byte-onként megegyezik (timing-safe összehasonlítás).
    """
    secret = (os.environ.get("MESENCSI_INTERNAL_DEBUG_SECRET") or "").strip()
    if not secret or x_internal_debug is None:
        return False
    a = secret.encode("utf-8")
    b = x_internal_debug.strip().encode("utf-8")
    if len(a) != len(b):
        return False
    return compare_digest(a, b)
