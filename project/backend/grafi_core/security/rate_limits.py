"""API rate limiting (slowapi) — IP-based with optional Redis storage."""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

from grafi_core.settings.core_settings import CoreSettings


def create_limiter(core_settings: CoreSettings | None = None) -> Limiter:
    settings = core_settings or CoreSettings.from_env()
    disabled = settings.is_test_mode()
    redis_url = (os.environ.get("REDIS_URL") or "").strip()
    if redis_url:
        return Limiter(key_func=get_remote_address, storage_uri=redis_url, enabled=not disabled)
    return Limiter(key_func=get_remote_address, enabled=not disabled)


# Default module-level limiter for apps that import directly.
limiter = create_limiter()
