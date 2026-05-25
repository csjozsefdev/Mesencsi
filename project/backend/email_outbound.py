"""Plain SMTP outbound mail — dev logs verification links when SMTP is optional."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

from email_config import is_smtp_configured, smtp_required_for_outbound
from email_errors import EmailNotConfiguredError, EmailSendError

logger = logging.getLogger(__name__)

RESEND_COOLDOWN_SEC = 120


def _smtp_use_tls() -> bool:
    """STARTTLS on port 587 by default; set SMTP_USE_TLS=0 for Mailpit / plain SMTP."""
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
    smtp_port = int(os.environ.get("SMTP_PORT", "587") or "587")
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_pass = os.environ.get("SMTP_PASSWORD", "").strip()
    mail_from = (os.environ.get("SMTP_FROM") or smtp_user or "noreply@localhost").strip()
    use_tls = _smtp_use_tls()
    return smtp_host, smtp_port, smtp_user, smtp_pass, mail_from, use_tls


def _log_dev_verification_links(*, to_email: str, token: str) -> None:
    link = f"{public_base_url()}/?email_verify_token={token}"
    api_verify = f"{api_public_base_url()}/auth/verify-email?token={token}"
    logger.warning(
        "DEV email fallback — verification not sent via SMTP; to=%s frontend_link=%s api_link=%s",
        to_email,
        link,
        api_verify,
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
    Send a plain-text email.

    Returns True when the message was sent via SMTP.
    Returns False only in local dev when SMTP is optional and not configured (logged).
    Raises EmailNotConfiguredError or EmailSendError on hosted deployments.
    """
    to_email = to_email.strip()
    smtp_host, smtp_port, smtp_user, smtp_pass, mail_from, use_tls = _smtp_settings()

    logger.info(
        "Plain email send started — to=%s subject=%r smtp_configured=%s smtp_required=%s use_tls=%s host=%s port=%s",
        to_email,
        subject[:80],
        is_smtp_configured(),
        smtp_required_for_outbound(),
        use_tls,
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

    if smtp_required_for_outbound() and not (smtp_user and smtp_pass and mail_from):
        _raise_if_smtp_required_but_missing()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            if smtp_user:
                smtp.login(smtp_user, smtp_pass)
            smtp.send_message(msg)
    except Exception as e:
        logger.error(
            "SMTP send failed — to=%s subject=%r error_type=%s error=%s host=%s port=%s use_tls=%s",
            to_email,
            subject[:80],
            type(e).__name__,
            e,
            smtp_host,
            smtp_port,
            use_tls,
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

    # Dev-only path: SMTP optional
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
