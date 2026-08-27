"""Éles vs fejlesztői viselkedés: ``MESENCSI_PRODUCTION``, opcionális belső debug titok."""

from __future__ import annotations

import os
from secrets import compare_digest


def mesencsi_production() -> bool:
    """``MESENCSI_PRODUCTION=true`` (vagy 1/yes/on) → éles szabályok (stub tiltás, manuális callback tiltás)."""
    v = (os.environ.get("MESENCSI_PRODUCTION") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def barion_payments_enabled() -> bool:
    """
    ``BARION_PAYMENTS_ENABLED`` — független ``MESENCSI_PRODUCTION``-tól.

    Alapértelmezetten ``true`` (visszafelé kompatibilis: meglévő éles Barion-integrációk
    nem igényelnek új env-változót). ``false``-ra állítva a webalkalmazás lehet éles
    (``MESENCSI_PRODUCTION=true``, ``/docs`` stb. továbbra is tiltva) úgy, hogy a Barion
    fizetés még sandboxban van vagy egyáltalán nincs beállítva — a fizetésindító és
    callback/IPN végpontok ekkor 503-at adnak, az induláskori validátor pedig nem követeli
    meg a Barion production konfigot.
    """
    v = (os.environ.get("BARION_PAYMENTS_ENABLED") or "").strip().lower()
    if not v:
        return True
    return v in ("1", "true", "yes", "on")


def auth_email_hosted_environment() -> bool:
    """
    True when this process should be treated as a hosted/production deployment for
    auth-email purposes (registration verification, password reset).

    ``mesencsi_production()`` alone only recognizes a literally-set ``MESENCSI_PRODUCTION``.
    A real deployment (e.g. a VPS) may instead only set the broader hosted-deployment
    signals used elsewhere in the codebase (``ENVIRONMENT``/``ENV`` = staging|production|
    prod|live, ``RENDER=true``, ``GRAFI_PRODUCTION``). Without this merge, such a
    deployment would silently swallow verification-email failures as if it were local
    dev, and would keep logging raw verification links/tokens as "local dev" diagnostics.
    Imported lazily to avoid a hard import-time dependency from this low-level module.
    """
    if mesencsi_production():
        return True
    from grafi_core.email.config import hosted_deployment

    return hosted_deployment()


def auth_email_requires_working_smtp() -> bool:
    """Shop verification/reset mail: strict SMTP whenever this is a hosted/production deployment."""
    return auth_email_hosted_environment()


def dev_log_auth_email_links_always() -> bool:
    """
    Local QA: print verification/reset URLs in the terminal even when SMTP send succeeds.

    Only when this is not a hosted/production deployment. Set
    ``MESENCSI_DEV_LOG_AUTH_EMAIL_LINKS=true`` in .env.
    """
    if auth_email_hosted_environment():
        return False
    v = (os.environ.get("MESENCSI_DEV_LOG_AUTH_EMAIL_LINKS") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def internal_barion_debug_authorized(x_internal_debug: str | None) -> bool:
    """
    Csak ha ``MESENCSI_INTERNAL_DEBUG_SECRET`` be van állítva a .env-ben, és a kérés
    ``X-Internal-Debug`` fejléce byte-onként megegyezik (timing-safe összehasonlítás).
    """
    secret = (os.environ.get("MESENCSI_INTERNAL_DEBUG_SECRET") or "").strip()
    if not secret or x_internal_debug is None:
        return False
    a = secret.encode("utf-8")
    b = x_internal_debug.strip().encode("utf-8")
    if len(a) != len(b):
        return False
    return compare_digest(a, b)
