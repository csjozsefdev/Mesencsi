"""Demo app settings — grafi_core only, no Mesencsi adapters."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from grafi_core.settings.cookie_names import CookieNames
from grafi_core.settings.core_settings import CoreSettings

_DEMO_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def demo_config_dir() -> Path:
    return _DEMO_DIR


@lru_cache(maxsize=1)
def demo_core_settings() -> CoreSettings:
    return CoreSettings(
        app_name="grafi_demo",
        logger_prefix="grafi_demo",
        production_env_key="GRAFI_PRODUCTION",
        config_dir=demo_config_dir(),
        test_database_url_env_key="GRAFI_TEST_DATABASE_URL",
    )


@lru_cache(maxsize=1)
def demo_cookie_names() -> CookieNames:
    return CookieNames(
        user_token="demo_user_token",
        admin_token="demo_admin_token",
        csrf="demo_csrf",
    )


def reset_demo_settings_cache() -> None:
    """Clear cached settings (tests only)."""
    demo_config_dir.cache_clear()
    demo_core_settings.cache_clear()
    demo_cookie_names.cache_clear()
