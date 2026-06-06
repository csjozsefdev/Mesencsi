"""Env file loading — local Path-based discovery for backend/.env."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent

_LOGGER_PREFIX = "mesencsi"
_loaded_paths: list[str] | None = None


def _logger() -> logging.Logger:
    return logging.getLogger(f"{_LOGGER_PREFIX}.env")


def load_backend_env() -> list[str]:
    """Load backend/.env and optional .env.py once. Returns absolute paths loaded."""
    global _loaded_paths
    if _loaded_paths is not None:
        return list(_loaded_paths)

    if os.environ.get("PYTEST_CURRENT_TEST"):
        _loaded_paths = []
        return []

    paths: list[str] = []
    log = _logger()
    env_file = BACKEND_DIR / ".env"
    if env_file.is_file():
        load_dotenv(env_file)
        paths.append(str(env_file.resolve()))
    env_py = BACKEND_DIR / ".env.py"
    if env_py.is_file():
        load_dotenv(env_py, override=True)
        paths.append(str(env_py.resolve()))

    _loaded_paths = paths
    if paths:
        log.debug("Loaded env files: %s", ", ".join(paths))
    else:
        log.warning("No .env file found under %s", BACKEND_DIR)
    return list(paths)


def backend_env_files_loaded() -> list[str]:
    if _loaded_paths is None:
        load_backend_env()
    return list(_loaded_paths or [])
