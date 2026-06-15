"""Indításkori konfig ellenőrzés — élesben kötelező mezők, devben csak warning."""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from cors_config import cors_origins_raw_env, parse_cors_origins_list, validate_production_cors_origins
from email_config import hosted_deployment, is_mailpit_style_local, is_smtp_configured, smtp_mode
from grafi_core.ops.startup_helpers import (
    StartupConfigError,
    env_value as _env,
    https_public_url as _https_public_url,
    secret_ok as _secret_ok,
)
from bcrypt_validation import is_valid_bcrypt_hash
from runtime_flags import mesencsi_production

_log = logging.getLogger("mesencsi.startup_config")

_MIN_SECRET_LEN = 32
_ALLOWED_JWT_ALGS = frozenset({"HS256", "HS384", "HS512"})
_KNOWN_PLACEHOLDER_BCRYPT_HASHES = frozenset(
    {
        "$2b$12$RODq4o.6S.4O74wOv/X7W.gqFb8wAVlN5cULfb65eyD8fG4K5RBNm",
        "$2b$12$xDHw3z3hPjTAeFUT/RTi..goxZeQ4PwmIaBHzfrUTS3abkv8S5vG6",
    }
)


def _bcrypt_hash_ok(name: str) -> tuple[bool, str | None]:
    value = _env(name)
    if not value:
        return False, f"{name} is not set"
    if value in _KNOWN_PLACEHOLDER_BCRYPT_HASHES:
        return False, f"{name} uses a known placeholder hash from .env.example"
    if not is_valid_bcrypt_hash(value):
        return False, f"{name} is not a valid bcrypt hash"
    return True, None


def _jwt_alg_ok(env_key: str, *, default: str = "HS256") -> tuple[bool, str | None]:
    alg = (_env(env_key) or default).strip().upper()
    if alg not in _ALLOWED_JWT_ALGS:
        return False, f"{env_key} must be one of HS256, HS384, HS512 (got {alg!r})"
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

    if production:
        user_secret = _env("USER_JWT_SECRET")
        admin_secret = _env("ADMIN_JWT_SECRET")
        if user_secret and admin_secret and user_secret == admin_secret:
            fatal.append("USER_JWT_SECRET and ADMIN_JWT_SECRET must differ in production")

        for alg_key in ("JWT_ALGORITHM", "ADMIN_JWT_ALGORITHM"):
            ok, err = _jwt_alg_ok(alg_key)
            if not ok and err:
                fatal.append(err)

        for admin_key in ("OWNER_USERNAME", "MAINTENANCE_USERNAME"):
            add(bool(_env(admin_key)), f"{admin_key} is not set", prod_fatal=True)
        for hash_key in ("OWNER_PASSWORD", "MAINTENANCE_PASSWORD"):
            ok, err = _bcrypt_hash_ok(hash_key)
            if not ok and err:
                fatal.append(err)

        if _env("QA_SHOP_EMAIL") or _env("QA_SHOP_PASSWORD"):
            fatal.append("QA_SHOP_EMAIL and QA_SHOP_PASSWORD must not be set in production")

        for url_key in ("PUBLIC_SITE_URL", "BACKEND_PUBLIC_URL", "FRONTEND_BASE_URL"):
            ok, err = _https_public_url(url_key, _env(url_key))
            if not ok and err:
                fatal.append(err)

        if not is_smtp_configured():
            fatal.append(
                "SMTP is not fully configured — set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM"
            )

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
        pass
    else:
        for key in ("POSTGRES_USER", "POSTGRES_HOST", "POSTGRES_DB"):
            add(bool(_env(key)), f"{key} is not set", prod_fatal=True)
        if production and not _env("POSTGRES_PASSWORD"):
            fatal.append("POSTGRES_PASSWORD is not set")

    if production:
        ok, err = _https_public_url("PUBLIC_SITE_URL", _env("PUBLIC_SITE_URL"))
        if not ok and err:
            fatal.append(err)

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

    if hosted_deployment():
        if not is_smtp_configured():
            fatal.append(
                "SMTP is not fully configured — set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM "
                "(required on Render / staging / production / MESENCSI_PRODUCTION)"
            )
        smtp_port = _env("SMTP_PORT") or "587"
        if smtp_port and not smtp_port.isdigit():
            fatal.append("SMTP_PORT must be a numeric port (e.g. 587 or 465)")
    elif not _env("SMTP_HOST"):
        warn.append("SMTP_HOST not set — verification emails log-only in local dev")
    elif smtp_mode() == "partial":
        warn.append(
            "SMTP partial config — use full relay (SMTP_USER + SMTP_PASSWORD App Password + SMTP_FROM) "
            "e.g. Gmail smtp.gmail.com:587, or optional Mailpit on 127.0.0.1:1025 with SMTP_USE_TLS=0"
        )
    elif is_mailpit_style_local():
        warn.append("SMTP Mailpit mode (127.0.0.1:1025) — ensure Mailpit is running or switch to relay SMTP")
    elif is_smtp_configured():
        from email_config import smtp_brevo_from_misconfigured, smtp_resend_user_misconfigured

        if smtp_brevo_from_misconfigured():
            warn.append(
                "SMTP_FROM is the Brevo SMTP login (@smtp-brevo.com) — use a verified sender address "
                "from Brevo → Senders, Domains & IPs (Brevo accepts SMTP but may not deliver)"
            )
        if smtp_resend_user_misconfigured():
            warn.append(
                "Resend SMTP: set SMTP_USER=resend and SMTP_PASSWORD to your re_ API key (see backend/docs/resend_smtp.md)"
            )

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
        "smtp_configured": is_smtp_configured(),
        "hosted_deployment": hosted_deployment(),
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
        if production or hosted_deployment():
            raise StartupConfigError(fatal)
