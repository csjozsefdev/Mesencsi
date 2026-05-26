"""Load ``backend/.env`` (and optional ``.env.py``) from the app package directory."""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

_log = logging.getLogger("mesencsi.env")

# Directory containing mesencsi.py, database.py, .env.example — not the repo root.
BACKEND_DIR = Path(__file__).resolve().parent

_loaded_paths: list[str] = []


def load_backend_env() -> list[str]:
    """
    Load env files once per process. Paths are absolute for diagnostics.

    Run uvicorn from ``project/backend`` so this matches your ``.env`` file location.
    """
    global _loaded_paths
    if _loaded_paths:
        return _loaded_paths

    paths: list[str] = []
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
        _log.debug("Loaded env files: %s", ", ".join(paths))
    else:
        _log.warning(
            "No .env file found under %s — copy .env.example to .env in the backend folder",
            BACKEND_DIR,
        )
    return paths


def backend_env_files_loaded() -> list[str]:
    """Absolute paths of env files loaded (empty if none)."""
    return list(load_backend_env())
