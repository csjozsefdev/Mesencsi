"""SMTP / outbound email policy: local dev vs hosted (Render, staging, production)."""

from __future__ import annotations

import os

from runtime_flags import mesencsi_production


def deployment_label() -> str:
    """Normalized ENVIRONMENT / ENV value, or development."""
    raw = (os.environ.get("ENVIRONMENT") or os.environ.get("ENV") or "").strip().lower()
    return raw or "development"


def hosted_deployment() -> bool:
    """
    Deployed environments where confirmation email must not be silently skipped.

    True when MESENCSI_PRODUCTION is set, ENVIRONMENT is staging/production,
    or Render's RENDER=true (typical on Render.com without extra env).
    """
    if mesencsi_production():
        return True
    if deployment_label() in ("staging", "production", "prod", "live"):
        return True
    render_flag = (os.environ.get("RENDER") or "").strip().lower()
    return render_flag in ("true", "1", "yes", "on")


def smtp_required_for_outbound() -> bool:
    """When True, missing or failed SMTP must be logged clearly and not treated as dev-only."""
    return hosted_deployment()


def is_smtp_configured() -> bool:
    host = (os.environ.get("SMTP_HOST") or "").strip()
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = (os.environ.get("SMTP_PASSWORD") or "").strip()
    mail_from = (os.environ.get("SMTP_FROM") or "").strip()
    return bool(host and user and password and mail_from)
