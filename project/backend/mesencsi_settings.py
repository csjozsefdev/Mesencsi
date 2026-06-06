"""Mesencsi application settings wired to grafi_core."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from grafi_core.settings.cookie_names import CookieNames
from grafi_core.settings.core_settings import CoreSettings
from grafi_core.settings.jwt_settings import AdminJwtErrorMessages, AdminJwtSettings, ShopJwtErrorMessages, ShopJwtSettings

_BACKEND_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def mesencsi_config_dir() -> Path:
    return _BACKEND_DIR


@lru_cache(maxsize=1)
def mesencsi_core_settings() -> CoreSettings:
    return CoreSettings(
        app_name="mesencsi",
        logger_prefix="mesencsi",
        production_env_key="MESENCSI_PRODUCTION",
        config_dir=mesencsi_config_dir(),
        test_database_url_env_key="MESENCSI_TEST_DATABASE_URL",
    )


@lru_cache(maxsize=1)
def mesencsi_cookie_names() -> CookieNames:
    return CookieNames.mesencsi_defaults()


@lru_cache(maxsize=1)
def mesencsi_shop_jwt_settings() -> ShopJwtSettings:
    return ShopJwtSettings(
        error_messages=ShopJwtErrorMessages(
            missing_secret=(
                "A szerver USER_JWT_SECRET kulcs nélkül nem adhat ki belépési tokent. "
                "Állítsd be a .env fájlban."
            ),
            expired="A belépési azonosító lejárt. Jelentkezz be újra.",
            invalid="Érvénytelen belépési azonosító.",
        )
    )


@lru_cache(maxsize=1)
def mesencsi_admin_jwt_settings() -> AdminJwtSettings:
    return AdminJwtSettings(
        error_messages=AdminJwtErrorMessages(
            missing_secret="A szerver ADMIN_JWT_SECRET kulcs nélkül nem adhat ki admin belépési tokent.",
            expired="Az admin belépési azonosító lejárt. Jelentkezz be újra.",
            invalid="Érvénytelen admin belépési azonosító.",
        )
    )
