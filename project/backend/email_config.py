"""SMTP configuration — delegates to grafi_core with Mesencsi settings."""

from __future__ import annotations

from mesencsi_settings import mesencsi_config_dir, mesencsi_core_settings
from grafi_core.email.config import (
    can_send_via_smtp as _can_send_via_smtp,
    deployment_label,
    hosted_deployment as _hosted_deployment,
    is_mailpit_style_local as _is_mailpit_style_local,
    is_smtp_configured,
    log_smtp_config_at_startup as _log_smtp_config_at_startup,
    smtp_brevo_from_misconfigured,
    smtp_config_diagnostic as _smtp_config_diagnostic,
    smtp_config_issues,
    smtp_from_is_brevo_relay_login,
    smtp_host_value,
    smtp_mode as _smtp_mode,
    smtp_port_from_env,
    smtp_provider_label,
    smtp_required_for_outbound as _smtp_required_for_outbound,
    smtp_resend_user_misconfigured,
    smtp_transport_mode,
)
from grafi_core.settings.smtp_settings import SmtpSettings
from env_loader import BACKEND_DIR

SMTP_ENV_KEYS = SmtpSettings().env_keys


def _settings():
    return mesencsi_core_settings()


def hosted_deployment() -> bool:
    return _hosted_deployment(core_settings=_settings())


def smtp_required_for_outbound() -> bool:
    return _smtp_required_for_outbound(core_settings=_settings())


def smtp_mode() -> str:
    return _smtp_mode(core_settings=_settings())


def is_mailpit_style_local() -> bool:
    return _is_mailpit_style_local(core_settings=_settings())


def can_send_via_smtp() -> bool:
    return _can_send_via_smtp(core_settings=_settings())


def smtp_config_diagnostic() -> dict[str, object]:
    diag = dict(
        _smtp_config_diagnostic(
            config_dir=mesencsi_config_dir(),
            core_settings=_settings(),
        )
    )
    # Backward-compatible key used by dev diagnostics and legacy docs.
    if "config_dir" in diag:
        diag["backend_dir"] = diag["config_dir"]
    return diag


def log_smtp_config_at_startup() -> None:
    _log_smtp_config_at_startup(
        config_dir=mesencsi_config_dir(),
        core_settings=_settings(),
    )


__all__ = [
    "BACKEND_DIR",
    "SMTP_ENV_KEYS",
    "can_send_via_smtp",
    "deployment_label",
    "hosted_deployment",
    "is_mailpit_style_local",
    "is_smtp_configured",
    "log_smtp_config_at_startup",
    "smtp_brevo_from_misconfigured",
    "smtp_config_diagnostic",
    "smtp_config_issues",
    "smtp_from_is_brevo_relay_login",
    "smtp_host_value",
    "smtp_mode",
    "smtp_port_from_env",
    "smtp_provider_label",
    "smtp_required_for_outbound",
    "smtp_resend_user_misconfigured",
    "smtp_transport_mode",
]
