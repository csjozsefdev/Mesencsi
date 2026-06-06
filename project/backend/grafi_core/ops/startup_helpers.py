"""Startup validation helpers — composable checks for consuming apps."""

from __future__ import annotations

import os
from urllib.parse import urlparse

PLACEHOLDER_MARKERS = (
    "replace_with",
    "changeme",
    "your-secret",
    "example.com",
)

MIN_SECRET_LEN = 32


class StartupConfigError(RuntimeError):
    """Fatal startup configuration error."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("Production configuration invalid:\n- " + "\n- ".join(issues))


def env_value(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def looks_placeholder(value: str) -> bool:
    low = value.lower()
    return any(marker in low for marker in PLACEHOLDER_MARKERS)


def secret_ok(name: str, *, min_len: int = MIN_SECRET_LEN) -> tuple[bool, str | None]:
    value = env_value(name)
    if not value:
        return False, f"{name} is not set"
    if looks_placeholder(value):
        return False, f"{name} looks like a placeholder"
    if len(value) < min_len:
        return False, f"{name} is too short (min {min_len} chars)"
    return True, None


def https_public_url(label: str, raw: str) -> tuple[bool, str | None]:
    if not raw:
        return False, f"{label} is not set"
    if not raw.startswith("https://"):
        return False, f"{label} must use https in production"
    try:
        parsed = urlparse(raw)
        if not parsed.netloc:
            return False, f"{label} has no host"
    except Exception:
        return False, f"{label} is not a valid URL"
    return True, None
