"""Env file loading — delegates to grafi_core."""

from __future__ import annotations

from adapters.grafi_settings import mesencsi_config_dir, mesencsi_core_settings
from grafi_core.ops import env_loader as _env_loader

BACKEND_DIR = mesencsi_config_dir()


def load_backend_env() -> list[str]:
    settings = mesencsi_core_settings()
    return _env_loader.load_env_files(BACKEND_DIR, logger_prefix=settings.logger_prefix)


def backend_env_files_loaded() -> list[str]:
    return _env_loader.env_files_loaded(BACKEND_DIR)
