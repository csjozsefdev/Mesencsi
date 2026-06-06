"""Load .env files from a configurable application directory."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from grafi_core.settings.core_settings import CoreSettings

_loaded_by_dir: dict[str, list[str]] = {}


def _logger(prefix: str = "grafi") -> logging.Logger:
    return logging.getLogger(f"{prefix}.env")


def load_env_files(config_dir: Path, *, logger_prefix: str = "grafi") -> list[str]:
    """
    Load env files once per config directory. Returns absolute paths loaded.

    Skips loading when PYTEST_CURRENT_TEST is set (keeps tests deterministic).
    """
    key = str(config_dir.resolve())
    if key in _loaded_by_dir:
        return _loaded_by_dir[key]

    if os.environ.get("PYTEST_CURRENT_TEST"):
        _loaded_by_dir[key] = []
        return []

    paths: list[str] = []
    log = _logger(logger_prefix)
    env_file = config_dir / ".env"
    if env_file.is_file():
        load_dotenv(env_file)
        paths.append(str(env_file.resolve()))
    env_py = config_dir / ".env.py"
    if env_py.is_file():
        load_dotenv(env_py, override=True)
        paths.append(str(env_py.resolve()))

    _loaded_by_dir[key] = paths
    if paths:
        log.debug("Loaded env files: %s", ", ".join(paths))
    else:
        log.warning("No .env file found under %s", config_dir)
    return paths


def env_files_loaded(config_dir: Path | None) -> list[str]:
    if config_dir is None:
        return []
    key = str(config_dir.resolve())
    if key not in _loaded_by_dir:
        settings = CoreSettings.from_env(config_dir=config_dir)
        load_env_files(config_dir, logger_prefix=settings.logger_prefix)
    return list(_loaded_by_dir.get(key, []))
