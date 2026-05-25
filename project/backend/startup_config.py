"""Indításkori konfig ellenőrzés — élesben kötelező mezők, devben csak warning."""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from cors_config import cors_origins_raw_env, parse_cors_origins_list, validate_production_cors_origins
from runtime_flags import mesencsi_production

_log = logging.getLogger("mesencsi.startup_config")

_PLACEHOLDER_MARKERS = (
    "replace_with",
    "changeme",
    "your-secret",
    "example.com",
)

_MIN_SECRET_LEN = 32


class StartupConfigError(RuntimeError):
    """Éles módban hiányzó vagy érvénytelen konfiguráció — az app nem indulhat."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__(
            "Production configuration invalid:\n- " + "\n- ".join(issues)
        )


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _looks_placeholder(value: str) -> bool:
    low = value.lower()
    return any(m in low for m in _PLACEHOLDER_MARKERS)


def _secret_ok(name: str) -> tuple[bool, str | None]:
    v = _env(name)
    if not v:
        return False, f"{name} is not set"
    if _looks_placeholder(v):
        return False, f"{name} looks like a placeholder"
    if len(v) < _MIN_SECRET_LEN:
        return False, f"{name} is too short (min {_MIN_SECRET_LEN} chars)"
    return True, None


def _https_public_url(label: str, raw: str) -> tuple[bool, str | None]:
    if not raw:
        return False, f"{label} is not set"
    if not raw.startswith("https://"):
        return False, f"{label} must use https in production"
    try:
        p = urlparse(raw)
        if not p.netloc:
            return False, f"{label} has no host"
    except Exception:
        return False, f"{label} is not a valid URL"
    return True, None


def _barion_return_url() -> str:
    explicit = _env("BARION_RETURN_URL")
    if explicit:
        return explicit
    base = (
        _env("BARION_BACKEND_PUBLIC_URL")
        or _env("BACKEND_PUBLIC_URL")
        or _env("PUBLIC_SITE_URL")
    ).rstrip("/")
    return f"{base}/payments/barion/return"


def _barion_callback_url() -> str:
    return (
        _env("BARION_CALLBACK_URL")
        or _env("BARION_IPN_URL")
        or f"{_env('BARION_BACKEND_PUBLIC_URL') or _env('BACKEND_PUBLIC_URL') or _env('PUBLIC_SITE_URL')}".rstrip("/")
        + "/payments/barion/ipn"
    )


def _collect_issues(*, production: bool) -> tuple[list[str], list[str]]:
    """Vissza: (fatal, warnings) — fatal csak élesben használt."""
    fatal: list[str] = []
    warn: list[str] = []

    def add(ok: bool, msg: str, *, prod_fatal: bool = True) -> None:
        if ok:
            return
        if production and prod_fatal:
            fatal.append(msg)
        else:
            warn.append(msg)

    ok, err = _secret_ok("USER_JWT_SECRET")
    add(ok, err or "", prod_fatal=True)

    ok, err = _secret_ok("ADMIN_JWT_SECRET")
    add(ok, err or "", prod_fatal=True)

    cors_raw = cors_origins_raw_env()
    cors_list = parse_cors_origins_list(cors_raw) if cors_raw else []
    if production:
        for issue in validate_production_cors_origins(cors_list):
            fatal.append(issue)
    elif not cors_raw:
        warn.append("CORS_ALLOWED_ORIGINS not set — using dev default CORS list")

    if production and _env("MESENCSI_TEST_DATABASE_URL"):
        fatal.append("MESENCSI_TEST_DATABASE_URL must not be set in production mode")
    elif _env("MESENCSI_TEST_DATABASE_URL"):
        # Dev/pytest: alternate DB URL (e.g. SQLite in-memory) — Postgres env vars not required.
        pass
    else:
        for key in ("POSTGRES_USER", "POSTGRES_HOST", "POSTGRES_DB"):
            add(bool(_env(key)), f"{key} is not set", prod_fatal=True)
        if production and not _env("POSTGRES_PASSWORD"):
            fatal.append("POSTGRES_PASSWORD is not set")

    if production:
        add(bool(_env("BARION_POS_KEY")), "BARION_POS_KEY is not set", prod_fatal=True)
        add(bool(_env("BARION_PAYEE_EMAIL")), "BARION_PAYEE_EMAIL is not set", prod_fatal=True)
        add(bool(_env("BARION_IPN_SECRET")), "BARION_IPN_SECRET is not set", prod_fatal=True)

        barion_env = _env("BARION_ENV").lower()
        if barion_env not in ("production", "prod", "live", "release"):
            fatal.append("BARION_ENV must be production (or prod/live/release) in production mode")

        ok, err = _https_public_url("BARION return URL", _barion_return_url())
        if not ok and err:
            fatal.append(err)

        ok, err = _https_public_url("BARION callback/IPN URL", _barion_callback_url())
        if not ok and err:
            fatal.append(err)

        backend_base = (
            _env("BARION_BACKEND_PUBLIC_URL") or _env("BACKEND_PUBLIC_URL") or _env("PUBLIC_SITE_URL")
        )
        ok, err = _https_public_url("BARION_BACKEND_PUBLIC_URL (or BACKEND_PUBLIC_URL)", backend_base)
        if not ok and err:
            fatal.append(err)
    else:
        if not _env("BARION_POS_KEY"):
            warn.append("BARION_POS_KEY not set — Barion stub/preview mode")
        if mesencsi_production() is False and _env("BARION_ENV").lower() in ("", "sandbox", "test"):
            pass

    if production:
        for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
            add(bool(_env(key)), f"{key} is not set", prod_fatal=True)
    elif not _env("SMTP_HOST"):
        warn.append("SMTP_HOST not set — emails log-only in dev")

    return fatal, warn


def _safe_summary(*, production: bool, fatal: list[str], warn: list[str]) -> dict[str, object]:
    cors_raw = cors_origins_raw_env()
    origin_count = len(parse_cors_origins_list(cors_raw)) if cors_raw else 0
    return {
        "mode": "production" if production else "development",
        "mesencsi_production": mesencsi_production(),
        "user_jwt_secret_set": bool(_env("USER_JWT_SECRET")),
        "admin_jwt_secret_set": bool(_env("ADMIN_JWT_SECRET")),
        "allowed_origins_count": origin_count,
        "database": "test_override" if _env("MESENCSI_TEST_DATABASE_URL") else "postgres_env",
        "barion_pos_key_set": bool(_env("BARION_POS_KEY")),
        "barion_env": _env("BARION_ENV") or None,
        "barion_ipn_secret_set": bool(_env("BARION_IPN_SECRET")),
        "smtp_host_set": bool(_env("SMTP_HOST")),
        "config_errors": len(fatal),
        "config_warnings": len(warn),
    }


def run_startup_config_validation() -> None:
    """
    ``MESENCSI_PRODUCTION=true``: hiányzó kritikus env → ``StartupConfigError`` (app nem indul).
    Dev: csak warning log, indulás folytatódik.
    """
    production = mesencsi_production()
    fatal, warn = _collect_issues(production=production)
    summary = _safe_summary(production=production, fatal=fatal, warn=warn)

    _log.info("startup_config_summary %s", " | ".join(f"{k}={v!r}" for k, v in summary.items()))

    dev_optional: list[str] = []
    for w in warn:
        if production or "ADMIN_JWT_SECRET" in w or "USER_JWT_SECRET" in w:
            _log.warning("startup_config_warning %s", w)
        else:
            dev_optional.append(w)
    if dev_optional:
        _log.info(
            "startup_config_dev_optional (expected in local dev): %s",
            " | ".join(dev_optional),
        )

    if fatal:
        for issue in fatal:
            _log.error("startup_config_error %s", issue)
        if production:
            raise StartupConfigError(fatal)
