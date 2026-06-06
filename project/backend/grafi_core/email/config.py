"""SMTP / outbound email policy: local dev vs hosted deployments."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path

from grafi_core.ops.env_loader import env_files_loaded, load_env_files
from grafi_core.settings.core_settings import CoreSettings
from grafi_core.settings.smtp_settings import SmtpSettings

_log = logging.getLogger("grafi.email_config")

_DEFAULT_SMTP = SmtpSettings()


def deployment_label() -> str:
    raw = (os.environ.get("ENVIRONMENT") or os.environ.get("ENV") or "").strip().lower()
    return raw or "development"


def hosted_deployment(
    *,
    core_settings: CoreSettings | None = None,
    extra_hosted_check: Callable[[], bool] | None = None,
) -> bool:
    """
    Deployed environments where outbound email must not be silently skipped.

    True when production flag is set, ENVIRONMENT is staging/production,
    Render's RENDER=true, or extra_hosted_check returns True.
    """
    settings = core_settings or CoreSettings.from_env()
    if settings.is_production():
        return True
    if deployment_label() in ("staging", "production", "prod", "live"):
        return True
    render_flag = (os.environ.get("RENDER") or "").strip().lower()
    if render_flag in ("true", "1", "yes", "on"):
        return True
    if extra_hosted_check and extra_hosted_check():
        return True
    return False


def smtp_required_for_outbound(
    *,
    core_settings: CoreSettings | None = None,
    extra_hosted_check: Callable[[], bool] | None = None,
) -> bool:
    return hosted_deployment(core_settings=core_settings, extra_hosted_check=extra_hosted_check)


def _env(smtp: SmtpSettings, key_attr: str) -> str:
    key = getattr(smtp, key_attr)
    return (os.environ.get(key) or "").strip()


def is_smtp_configured(smtp: SmtpSettings | None = None) -> bool:
    s = smtp or _DEFAULT_SMTP
    return bool(
        _env(s, "host_env_key")
        and _env(s, "user_env_key")
        and _env(s, "password_env_key")
        and _env(s, "from_env_key")
    )


def _smtp_use_tls_from_env(smtp: SmtpSettings) -> bool:
    raw = (os.environ.get(smtp.use_tls_env_key) or ("1" if smtp.default_use_tls else "0")).strip().lower()
    return raw not in ("0", "false", "no", "off")


def smtp_port_from_env(smtp: SmtpSettings | None = None) -> int:
    s = smtp or _DEFAULT_SMTP
    raw = (os.environ.get(s.port_env_key) or str(s.default_port)).strip()
    try:
        return int(raw)
    except ValueError:
        return s.default_port


def is_mailpit_style_local(
    *,
    core_settings: CoreSettings | None = None,
    smtp: SmtpSettings | None = None,
) -> bool:
    if hosted_deployment(core_settings=core_settings):
        return False
    s = smtp or _DEFAULT_SMTP
    host = _env(s, "host_env_key").lower()
    if host not in ("127.0.0.1", "localhost", "::1"):
        return False
    return smtp_port_from_env(s) == 1025 and not _smtp_use_tls_from_env(s)


def smtp_mode(
    *,
    core_settings: CoreSettings | None = None,
    smtp: SmtpSettings | None = None,
) -> str:
    s = smtp or _DEFAULT_SMTP
    host = _env(s, "host_env_key")
    if not host:
        return "none"
    if is_smtp_configured(s):
        return "relay"
    if is_mailpit_style_local(core_settings=core_settings, smtp=s):
        return "mailpit"
    return "partial"


def can_send_via_smtp(
    *,
    core_settings: CoreSettings | None = None,
    smtp: SmtpSettings | None = None,
) -> bool:
    return smtp_mode(core_settings=core_settings, smtp=smtp) in ("relay", "mailpit")


def smtp_from_is_brevo_relay_login(mail_from: str) -> bool:
    addr = (mail_from or "").strip().lower()
    return addr.endswith("@smtp-brevo.com")


def smtp_brevo_from_misconfigured(smtp: SmtpSettings | None = None) -> bool:
    s = smtp or _DEFAULT_SMTP
    host = _env(s, "host_env_key").lower()
    if "brevo.com" not in host:
        return False
    mail_from = _env(s, "from_env_key") or _env(s, "user_env_key")
    return smtp_from_is_brevo_relay_login(mail_from)


def smtp_resend_user_misconfigured(smtp: SmtpSettings | None = None) -> bool:
    s = smtp or _DEFAULT_SMTP
    host = _env(s, "host_env_key").lower()
    if "resend.com" not in host:
        return False
    return _env(s, "user_env_key").lower() != "resend"


def smtp_host_value(smtp: SmtpSettings | None = None) -> str:
    return _env(smtp or _DEFAULT_SMTP, "host_env_key")


def smtp_provider_label(smtp: SmtpSettings | None = None) -> str:
    host = smtp_host_value(smtp).lower()
    if not host:
        return "none"
    if "resend.com" in host:
        return "resend"
    if "mailersend.net" in host or "mailersend.com" in host:
        return "mailersend"
    if "brevo.com" in host:
        return "brevo"
    if host in ("smtp.gmail.com", "gmail.com"):
        return "gmail"
    if host in ("127.0.0.1", "localhost", "::1"):
        return "mailpit"
    return "other"


def smtp_config_issues(smtp: SmtpSettings | None = None) -> list[str]:
    s = smtp or _DEFAULT_SMTP
    issues: list[str] = []
    host = smtp_host_value(s).lower()
    mail_from = _env(s, "from_env_key").lower()
    provider = smtp_provider_label(s)
    if smtp_brevo_from_misconfigured(s):
        issues.append("brevo_from_is_relay_login")
    if smtp_resend_user_misconfigured(s):
        issues.append("resend_user_must_be_literal_resend")
    if provider == "resend" and host and "resend.com" not in host:
        issues.append("resend_host_expected_smtp_resend_com")
    if provider == "mailersend" and mail_from.endswith("@gmail.com"):
        issues.append("mailersend_from_should_be_verified_domain_not_gmail")
    if provider == "resend" and mail_from.endswith("@gmail.com"):
        issues.append("resend_from_should_be_verified_domain_or_onboarding_resend_dev")
    if provider == "gmail" and host and "gmail" not in host:
        issues.append("gmail_from_with_non_gmail_host")
    return issues


def smtp_transport_mode(*, port: int, use_starttls: bool) -> str:
    if port == 465:
        return "ssl"
    if use_starttls:
        return "starttls"
    return "plain"


def smtp_config_diagnostic(
    *,
    config_dir: Path | None = None,
    core_settings: CoreSettings | None = None,
    smtp: SmtpSettings | None = None,
) -> dict[str, object]:
    settings = core_settings or CoreSettings.from_env(config_dir=config_dir)
    s = smtp or _DEFAULT_SMTP
    directory = config_dir or settings.config_dir
    if directory is not None:
        load_env_files(directory)
    port = smtp_port_from_env(s)
    use_tls = _smtp_use_tls_from_env(s)
    mail_from = _env(s, "from_env_key")
    host = smtp_host_value(s)
    return {
        "config_dir": str(directory) if directory else None,
        "env_files_loaded": env_files_loaded(directory) if directory else [],
        "env_keys_expected": list(s.env_keys),
        "smtp_host": host or None,
        "smtp_provider": smtp_provider_label(s),
        "smtp_config_issues": smtp_config_issues(s),
        "smtp_host_present": bool(host),
        "smtp_port": (os.environ.get(s.port_env_key) or str(s.default_port)).strip(),
        "smtp_user_present": bool(_env(s, "user_env_key")),
        "smtp_password_present": bool(_env(s, "password_env_key")),
        "smtp_from": mail_from or None,
        "smtp_use_tls": (os.environ.get(s.use_tls_env_key) or "1").strip(),
        "smtp_transport_mode": smtp_transport_mode(port=port, use_starttls=use_tls),
        "smtp_fully_configured": is_smtp_configured(s),
        "smtp_mode": smtp_mode(core_settings=settings, smtp=s),
        "smtp_mailpit_style": is_mailpit_style_local(core_settings=settings, smtp=s),
        "smtp_can_send": can_send_via_smtp(core_settings=settings, smtp=s),
        "smtp_brevo_from_misconfigured": smtp_brevo_from_misconfigured(s),
        "smtp_resend_user_misconfigured": smtp_resend_user_misconfigured(s),
        "hosted_deployment": hosted_deployment(core_settings=settings),
        "smtp_required_for_outbound": smtp_required_for_outbound(core_settings=settings),
    }


def log_smtp_config_at_startup(
    *,
    config_dir: Path | None = None,
    core_settings: CoreSettings | None = None,
    smtp: SmtpSettings | None = None,
) -> None:
    settings = core_settings or CoreSettings.from_env(config_dir=config_dir)
    if hosted_deployment(core_settings=settings):
        return
    diag = smtp_config_diagnostic(config_dir=config_dir, core_settings=settings, smtp=smtp)
    if diag.get("smtp_brevo_from_misconfigured"):
        _log.warning(
            "smtp_brevo_from_misconfigured SMTP_FROM=%r is the Brevo SMTP login, not a verified sender",
            diag.get("smtp_from"),
        )
    if diag.get("smtp_resend_user_misconfigured"):
        _log.warning("smtp_resend_user_misconfigured SMTP_USER must be exactly 'resend' for smtp.resend.com")
    _log.info(
        "smtp_config_diagnostic env_files=%s smtp_host_present=%s smtp_port=%s smtp_user_present=%s "
        "smtp_password_present=%s smtp_from=%r smtp_use_tls=%s transport=%s fully_configured=%s",
        diag.get("env_files_loaded") or "(none)",
        diag["smtp_host_present"],
        diag["smtp_port"],
        diag["smtp_user_present"],
        diag["smtp_password_present"],
        diag.get("smtp_from"),
        diag["smtp_use_tls"],
        diag["smtp_transport_mode"],
        diag["smtp_fully_configured"],
    )
