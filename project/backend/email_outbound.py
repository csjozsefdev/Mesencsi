"""Plain SMTP outbound mail — dev logs verification links when SMTP is optional."""

from __future__ import annotations

import logging
import os
import smtplib
from contextlib import contextmanager
from email.message import EmailMessage
from typing import Iterator

from email_config import (
    can_send_via_smtp,
    is_mailpit_style_local,
    is_smtp_configured,
    smtp_config_diagnostic,
    smtp_mode,
    smtp_port_from_env,
    smtp_required_for_outbound,
    smtp_transport_mode,
)
from email_errors import EmailNotConfiguredError, EmailSendError
from runtime_flags import mesencsi_production

logger = logging.getLogger(__name__)

RESEND_COOLDOWN_SEC = 120


def _smtp_use_tls() -> bool:
    """STARTTLS on 587 when enabled; port 465 uses implicit SSL instead."""
    raw = (os.environ.get("SMTP_USE_TLS") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def public_base_url() -> str:
    """Public site URL used in email links (usually the storefront origin)."""
    return (
        os.environ.get("FRONTEND_BASE_URL")
        or os.environ.get("PUBLIC_SITE_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def api_public_base_url() -> str:
    """API base URL for dev-only verification link logging."""
    return (
        os.environ.get("BACKEND_PUBLIC_URL")
        or os.environ.get("PUBLIC_SITE_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def _smtp_settings() -> tuple[str, int, str, str, str, bool]:
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    smtp_port = smtp_port_from_env()
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_pass = os.environ.get("SMTP_PASSWORD", "").strip()
    mail_from = (os.environ.get("SMTP_FROM") or smtp_user or "noreply@localhost").strip()
    use_tls = _smtp_use_tls()
    return smtp_host, smtp_port, smtp_user, smtp_pass, mail_from, use_tls


def _log_smtp_keys_loaded() -> None:
    """Log which SMTP env keys are set (never log secret values)."""
    diag = smtp_config_diagnostic()
    logger.info(
        "SMTP env snapshot — host_present=%s port=%s user_present=%s password_present=%s "
        "from=%r use_tls=%s transport=%s env_files=%s",
        diag["smtp_host_present"],
        diag["smtp_port"],
        diag["smtp_user_present"],
        diag["smtp_password_present"],
        diag.get("smtp_from"),
        diag["smtp_use_tls"],
        diag["smtp_transport_mode"],
        diag.get("env_files_loaded"),
    )


@contextmanager
def _smtp_session(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    use_tls: bool,
) -> Iterator[smtplib.SMTP]:
    """
    Open SMTP connection with correct TLS mode:
    - 465: SMTP_SSL (implicit TLS)
    - 587 (and others): SMTP + optional STARTTLS when SMTP_USE_TLS is on
    - Mailpit 1025: SMTP_USE_TLS=0 → plain
    """
    mode = smtp_transport_mode(port=port, use_starttls=use_tls)
    logger.debug("SMTP connect mode=%s host=%s port=%s", mode, host, port)
    if mode == "ssl":
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        smtp = smtplib.SMTP(host, port, timeout=30)
    try:
        if mode == "starttls":
            smtp.starttls()
        if user:
            smtp.login(user, password)
        yield smtp
    finally:
        try:
            smtp.quit()
        except Exception:
            smtp.close()


def _log_dev_verification_links(*, to_email: str, token: str) -> None:
    link = f"{public_base_url()}/?email_verify_token={token}"
    api_verify = f"{api_public_base_url()}/auth/verify-email?token={token}"
    logger.warning(
        "DEV email fallback — verification not sent via SMTP; to=%s frontend_link=%s api_link=%s",
        to_email,
        link,
        api_verify,
    )


def _log_dev_password_reset_link(*, to_email: str, token: str) -> None:
    """Log reset link in local dev when SMTP did not send (never logged in production)."""
    if mesencsi_production():
        return
    link = f"{public_base_url()}/reset-password.html?token={token}"
    logger.warning(
        "DEV password reset fallback — not sent via SMTP; to=%s reset_link=%s",
        to_email,
        link,
    )


def _raise_if_smtp_required_but_missing() -> None:
    if smtp_required_for_outbound() and not is_smtp_configured():
        logger.error(
            "SMTP is required on this deployment (MESENCSI_PRODUCTION, ENVIRONMENT=staging|production, "
            "or RENDER=true) but SMTP_HOST/SMTP_USER/SMTP_PASSWORD/SMTP_FROM are incomplete"
        )
        raise EmailNotConfiguredError(
            "SMTP is not configured for this deployment. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM."
        )


def send_plain_email(*, to_email: str, subject: str, body: str) -> bool:
    """
    Send a plain-text email via ``smtplib`` (entry point for all outbound mail).

    Returns True when the message was sent via SMTP.
    Returns False only in local dev when SMTP is optional and not configured (logged).
    Raises EmailNotConfiguredError or EmailSendError on hosted deployments.
    """
    to_email = to_email.strip()
    smtp_host, smtp_port, smtp_user, smtp_pass, mail_from, use_tls = _smtp_settings()
    transport = smtp_transport_mode(port=smtp_port, use_starttls=use_tls)

    _log_smtp_keys_loaded()
    logger.info(
        "Plain email send started — to=%s subject=%r smtp_configured=%s smtp_required=%s transport=%s host=%s port=%s",
        to_email,
        subject[:80],
        is_smtp_configured(),
        smtp_required_for_outbound(),
        transport,
        smtp_host or "(unset)",
        smtp_port,
    )

    if not smtp_host:
        _raise_if_smtp_required_but_missing()
        logger.info(
            "[email] SMTP_HOST not set — message not sent (dev log-only): to=%s subject=%r",
            to_email,
            subject[:80],
        )
        logger.debug("[email] body preview:\n%s", body[:1500])
        return False

    if smtp_required_for_outbound() and not is_smtp_configured():
        _raise_if_smtp_required_but_missing()

    if not smtp_required_for_outbound() and smtp_host and not can_send_via_smtp():
        logger.error(
            "SMTP partial config — for Gmail/Render set SMTP_HOST, SMTP_PORT=587, SMTP_USE_TLS=1, "
            "SMTP_USER, SMTP_PASSWORD (App Password), SMTP_FROM; or use Mailpit: "
            "SMTP_HOST=127.0.0.1 SMTP_PORT=1025 SMTP_USE_TLS=0 SMTP_FROM=noreply@localhost"
        )
        raise EmailSendError("SMTP relay config incomplete (missing USER, PASSWORD, or FROM)")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_email
    msg.set_content(body)
    try:
        with _smtp_session(
            host=smtp_host,
            port=smtp_port,
            user=smtp_user,
            password=smtp_pass,
            use_tls=use_tls,
        ) as smtp:
            smtp.send_message(msg)
    except Exception as e:
        logger.error(
            "SMTP send failed — to=%s subject=%r error_type=%s error=%s host=%s port=%s transport=%s",
            to_email,
            subject[:80],
            type(e).__name__,
            e,
            smtp_host,
            smtp_port,
            transport,
            exc_info=True,
        )
        raise EmailSendError(f"SMTP delivery failed: {type(e).__name__}") from e

    logger.info("Plain email sent successfully — to=%s subject=%r", to_email, subject[:80])
    return True


def send_email_verification(to_email: str, token: str) -> bool:
    """
    Registration / resend verification email.

    Hosted: requires working SMTP (raises on misconfiguration or send failure).
    Local dev without SMTP: logs frontend + API verification links and returns False.
    """
    link = f"{public_base_url()}/?email_verify_token={token}"
    subject = "Mesencsi — erősítsd meg az e-mail címed"
    body = (
        "Köszönjük a regisztrációt.\n\n"
        f"Kattints a linkre a megerősítéshez (érvényes 48 óráig):\n{link}\n\n"
        "Ha nem te regisztráltál, hagyd figyelmen kívül ezt az üzenetet.\n"
    )
    _raise_if_smtp_required_but_missing()
    try:
        sent = send_plain_email(to_email=to_email, subject=subject, body=body)
    except (EmailNotConfiguredError, EmailSendError):
        raise
    except Exception as e:
        logger.error(
            "Verification email unexpected failure — to=%s error_type=%s error=%s",
            to_email,
            type(e).__name__,
            e,
            exc_info=True,
        )
        raise EmailSendError(f"Verification email failed: {type(e).__name__}") from e

    if sent:
        logger.info("Verification email sent successfully — to=%s", to_email)
        return True

    _log_dev_verification_links(to_email=to_email, token=token)
    return False


def order_confirmation_processing_note() -> str | None:
    """Optional processing/shipping note (ORDER_CONFIRMATION_PROCESSING_NOTE)."""
    raw = (os.environ.get("ORDER_CONFIRMATION_PROCESSING_NOTE") or "").strip()
    return raw or None


def send_order_payment_confirmation(
    *,
    to_email: str,
    customer_name: str,
    order_reference: str,
    lines: list[tuple[str, int, int]],
    grand_total_huf: int,
    payment_id: str,
) -> bool:
    """
    Barion payment confirmation — call only after backend verify marks orders paid.
    Returns True when sent via SMTP; False in dev when SMTP is optional and missing.
    Raises EmailNotConfiguredError / EmailSendError on hosted when SMTP is required.
    """
    line_blocks = []
    for name, qty, line_total in lines:
        line_blocks.append(f"  • {name} × {qty} — {line_total:,} Ft".replace(",", " "))
    items_text = "\n".join(line_blocks) if line_blocks else "  • (no items)"
    grand_fmt = f"{grand_total_huf:,} Ft".replace(",", " ")

    body_parts = [
        f"Kedves {customer_name}!",
        "",
        "Köszönjük a vásárlást — a fizetésed sikeresen beérkezett.",
        "",
        f"Rendelés azonosító: {order_reference}",
        f"Fizetés azonosító (Barion): {payment_id}",
        "",
        "Megrendelt tételek:",
        items_text,
        "",
        f"Végösszeg: {grand_fmt}",
    ]
    note = order_confirmation_processing_note()
    if note:
        body_parts.extend(["", note])
    body_parts.extend(
        [
            "",
            "Ha kérdésed van, válaszolj erre az e-mailre vagy írj nekünk a webshopon keresztül.",
            "",
            "Üdvözlettel,",
            "A Mesencsi csapata",
            public_base_url(),
        ]
    )
    body = "\n".join(body_parts)
    subject = f"Mesencsi — rendelés visszaigazolás ({order_reference})"
    return send_plain_email(to_email=to_email, subject=subject, body=body)


def send_password_reset_email(to_email: str, token: str) -> bool:
    """
    Password reset email with one-time link (token valid ~60 minutes).

    Hosted: requires working SMTP. Local dev without SMTP: logs reset link and returns False.
    """
    link = f"{public_base_url()}/reset-password.html?token={token}"
    subject = "Mesencsi — jelszó visszaállítás"
    body = (
        "Jelszó-visszaállítást kértél a Mesencsi fiókodhoz.\n\n"
        f"Új jelszó beállítása (egyszer használható, kb. 60 percig érvényes):\n{link}\n\n"
        "Ha nem te kérted, hagyd figyelmen kívül ezt az üzenetet — a jelszavad változatlan marad.\n"
    )
    _raise_if_smtp_required_but_missing()
    try:
        sent = send_plain_email(to_email=to_email, subject=subject, body=body)
    except (EmailNotConfiguredError, EmailSendError):
        raise
    except Exception as e:
        logger.error(
            "Password reset email unexpected failure — to=%s error_type=%s error=%s",
            to_email,
            type(e).__name__,
            e,
            exc_info=True,
        )
        raise EmailSendError(f"Password reset email failed: {type(e).__name__}") from e

    if sent:
        logger.info("Password reset email sent successfully — to=%s", to_email)
        return True

    _log_dev_password_reset_link(to_email=to_email, token=token)
    return False
