"""SMTP / outbound email policy: local dev vs hosted (Render, staging, production)."""

from __future__ import annotations

import logging
import os

from env_loader import BACKEND_DIR, backend_env_files_loaded, load_backend_env
from runtime_flags import mesencsi_production

_log = logging.getLogger("mesencsi.email_config")

# Env keys read by email_outbound.py (must match .env.example).
SMTP_ENV_KEYS = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
    "SMTP_USE_TLS",
)


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
    """
    Full relay SMTP (Gmail, SendGrid, Render production): host + user + password + from.

    Used for ``smtp_fully_configured`` in diagnostics and hosted startup requirements.
    Mailpit-style local SMTP intentionally returns False here (no auth).
    """
    host = (os.environ.get("SMTP_HOST") or "").strip()
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = (os.environ.get("SMTP_PASSWORD") or "").strip()
    mail_from = (os.environ.get("SMTP_FROM") or "").strip()
    return bool(host and user and password and mail_from)


def is_mailpit_style_local() -> bool:
    """
    Optional local capture (Mailpit): plain SMTP on localhost:1025 without credentials.

    Not valid on hosted deployments.
    """
    if hosted_deployment():
        return False
    host = (os.environ.get("SMTP_HOST") or "").strip().lower()
    if host not in ("127.0.0.1", "localhost", "::1"):
        return False
    return smtp_port_from_env() == 1025 and not _smtp_use_tls_from_env()


def smtp_mode() -> str:
    """none | relay (full Gmail/Render) | mailpit (local optional) | partial (misconfigured)."""
    host = (os.environ.get("SMTP_HOST") or "").strip()
    if not host:
        return "none"
    if is_smtp_configured():
        return "relay"
    if is_mailpit_style_local():
        return "mailpit"
    return "partial"


def can_send_via_smtp() -> bool:
    """True when outbound SMTP should be attempted (relay or Mailpit)."""
    return smtp_mode() in ("relay", "mailpit")


def _smtp_use_tls_from_env() -> bool:
    raw = (os.environ.get("SMTP_USE_TLS") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def smtp_port_from_env() -> int:
    raw = (os.environ.get("SMTP_PORT") or "587").strip()
    try:
        return int(raw)
    except ValueError:
        return 587


def smtp_transport_mode(*, port: int, use_starttls: bool) -> str:
    """
    How send_plain_email connects: ssl (465), starttls (587), or plain (e.g. Mailpit 1025).

    Port 465 always uses implicit SSL regardless of SMTP_USE_TLS.
    """
    if port == 465:
        return "ssl"
    if use_starttls:
        return "starttls"
    return "plain"


def smtp_config_diagnostic() -> dict[str, object]:
    """Safe SMTP config snapshot — never includes passwords or tokens."""
    load_backend_env()
    port = smtp_port_from_env()
    use_tls = _smtp_use_tls_from_env()
    mail_from = (os.environ.get("SMTP_FROM") or "").strip()
    return {
        "backend_dir": str(BACKEND_DIR),
        "env_files_loaded": backend_env_files_loaded(),
        "env_keys_expected": list(SMTP_ENV_KEYS),
        "smtp_host_present": bool((os.environ.get("SMTP_HOST") or "").strip()),
        "smtp_port": str(os.environ.get("SMTP_PORT") or "587").strip(),
        "smtp_user_present": bool((os.environ.get("SMTP_USER") or "").strip()),
        "smtp_password_present": bool((os.environ.get("SMTP_PASSWORD") or "").strip()),
        "smtp_from": mail_from or None,
        "smtp_use_tls": (os.environ.get("SMTP_USE_TLS") or "1").strip(),
        "smtp_transport_mode": smtp_transport_mode(port=port, use_starttls=use_tls),
        "smtp_fully_configured": is_smtp_configured(),
        "smtp_mode": smtp_mode(),
        "smtp_mailpit_style": is_mailpit_style_local(),
        "smtp_can_send": can_send_via_smtp(),
        "hosted_deployment": hosted_deployment(),
        "smtp_required_for_outbound": smtp_required_for_outbound(),
    }


def log_smtp_config_at_startup() -> None:
    """Local dev: log which SMTP keys are present (no secrets). Hosted: skip (startup_config covers it)."""
    if hosted_deployment():
        return
    diag = smtp_config_diagnostic()
    _log.info(
        "smtp_config_diagnostic "
        "env_files=%s smtp_host_present=%s smtp_port=%s smtp_user_present=%s "
        "smtp_password_present=%s smtp_from=%r smtp_use_tls=%s transport=%s fully_configured=%s",
        diag.get("env_files_loaded") or "(none — add backend/.env)",
        diag["smtp_host_present"],
        diag["smtp_port"],
        diag["smtp_user_present"],
        diag["smtp_password_present"],
        diag.get("smtp_from"),
        diag["smtp_use_tls"],
        diag["smtp_transport_mode"],
        diag["smtp_fully_configured"],
    )
