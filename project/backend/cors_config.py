"""CORS allowed origins — dev localhost alapértelmezés; élesben csak explicit env lista."""

from __future__ import annotations

import os

from runtime_flags import mesencsi_production

# Visszafelé kompatibilis: ``CORS_ALLOWED_ORIGINS`` elsődleges, ``ALLOWED_ORIGINS`` alias.
_CORS_ENV_KEYS = ("CORS_ALLOWED_ORIGINS", "ALLOWED_ORIGINS")

_DEV_DEFAULT_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "null",
)


def cors_origins_raw_env() -> str:
    for key in _CORS_ENV_KEYS:
        v = (os.environ.get(key) or "").strip()
        if v:
            return v
    return ""


def parse_cors_origins_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def validate_production_cors_origins(origins: list[str]) -> list[str]:
    """Éles CORS szabályok — startup validator és resolve egyaránt használja."""
    issues: list[str] = []
    if not origins:
        issues.append(
            "CORS_ALLOWED_ORIGINS (or ALLOWED_ORIGINS) is not set — required in production"
        )
        return issues
    for origin in origins:
        if origin == "*":
            issues.append("CORS wildcard origin '*' is not allowed in production")
        elif origin.lower() == "null":
            issues.append("CORS origin 'null' is not allowed in production")
        elif "localhost" in origin or "127.0.0.1" in origin:
            issues.append(f"CORS origin must not be localhost in production: {origin!r}")
    return issues


def resolve_cors_allow_origins() -> list[str]:
    """
    Dev/local: env lista, vagy localhost-barát alapértelmezés.
    Production (``MESENCSI_PRODUCTION``): csak env; üres/hibás lista → ``[]`` (validator megállítja az indulást).
    """
    raw = cors_origins_raw_env()
    if mesencsi_production():
        origins = parse_cors_origins_list(raw)
        if validate_production_cors_origins(origins):
            return []
        return origins
    if raw:
        return parse_cors_origins_list(raw)
    return list(_DEV_DEFAULT_ORIGINS)
