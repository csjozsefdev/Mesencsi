"""Application-wide core settings (env prefix, config dir, production flag)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _truthy_env(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class CoreSettings:
    app_name: str = "grafi"
    logger_prefix: str = "grafi"
    production_env_key: str = "GRAFI_PRODUCTION"
    config_dir: Path | None = None
    test_database_url_env_key: str = "GRAFI_TEST_DATABASE_URL"

    @classmethod
    def from_env(cls, config_dir: Path | None = None) -> CoreSettings:
        app_name = (os.environ.get("GRAFI_APP_NAME") or "grafi").strip() or "grafi"
        logger_prefix = (os.environ.get("GRAFI_LOGGER_PREFIX") or app_name).strip() or app_name
        production_key = (os.environ.get("GRAFI_PRODUCTION_ENV_KEY") or "GRAFI_PRODUCTION").strip()
        test_db_key = (os.environ.get("GRAFI_TEST_DB_ENV_KEY") or "GRAFI_TEST_DATABASE_URL").strip()
        return cls(
            app_name=app_name,
            logger_prefix=logger_prefix,
            production_env_key=production_key or "GRAFI_PRODUCTION",
            config_dir=config_dir,
            test_database_url_env_key=test_db_key or "GRAFI_TEST_DATABASE_URL",
        )

    def is_production(self) -> bool:
        return _truthy_env(os.environ.get(self.production_env_key))

    def is_pytest(self) -> bool:
        return bool(os.environ.get("PYTEST_CURRENT_TEST"))

    def is_test_mode(self) -> bool:
        return self.is_pytest() or bool(
            (os.environ.get(self.test_database_url_env_key) or "").strip()
        )
