"""Egyszerű e-mail küldés — SMTP env vagy napló (fejlesztői mód)."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

RESEND_COOLDOWN_SEC = 120


def _smtp_use_tls() -> bool:
    """STARTTLS (587) éleshez; Mailpit/helyi plain SMTP-hez: SMTP_USE_TLS=0."""
    raw = (os.environ.get("SMTP_USE_TLS") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def public_base_url() -> str:
    """Publikus oldal (levélben lévő link — általában a bolt URL-je)."""
    return (
        os.environ.get("FRONTEND_BASE_URL")
        or os.environ.get("PUBLIC_SITE_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def api_public_base_url() -> str:
    """API / közvetlen verify link naplózáshoz (dev)."""
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
    mail_from = os.environ.get("SMTP_FROM", smtp_user or "noreply@localhost")
    use_tls = _smtp_use_tls()
    return smtp_host, smtp_port, smtp_user, smtp_pass, mail_from, use_tls


def send_plain_email(*, to_email: str, subject: str, body: str) -> bool:
    """
    True ha SMTP-pel ténylegesen elküldtük; False ha nincs SMTP (csak napló).
    Kivétel: SMTP be van állítva, de küldés közben hiba.
    """
    to_email = to_email.strip()
    smtp_host, smtp_port, smtp_user, smtp_pass, mail_from, use_tls = _smtp_settings()

    logger.info(
        "Plain email send started — to=%s subject=%r smtp_configured=%s use_tls=%s",
        to_email,
        subject[:80],
        bool(smtp_host),
        use_tls,
    )

    if not smtp_host:
        logger.info("[email] SMTP_HOST nincs beállítva — levél nem ment ki: to=%s subject=%r", to_email, subject)
        logger.debug("[email] body preview:\n%s", body[:1500])
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_email
    msg.set_content(body)
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        if smtp_user:
            smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)
    return True


def send_email_verification(to_email: str, token: str) -> bool:
    """
    True ha SMTP-pel ténylegesen elküldtük; False ha nincs SMTP (csak napló).
    Kivétel: SMTP be van állítva, de küldés közben hiba.
    """
    link = f"{public_base_url()}/?email_verify_token={token}"
    api_verify = f"{api_public_base_url()}/auth/verify-email?token={token}"
    subject = "Mesencsi — erősítsd meg az e-mail címed"
    body = (
        "Köszönjük a regisztrációt.\n\n"
        f"Kattints a linkre a megerősítéshez (érvényes 48 óráig):\n{link}\n\n"
        "Ha nem te regisztráltál, hagyd figyelmen kívül ezt az üzenetet.\n"
    )
    try:
        sent = send_plain_email(to_email=to_email, subject=subject, body=body)
        if sent:
            logger.info("Verification email sent successfully — %s", to_email)
        else:
            logger.info("DEV verification link (frontend): %s", link)
            logger.info("DEV verification link (API): %s", api_verify)
        return sent
    except Exception as e:
        logger.exception("Verification email failed: %s — %s", to_email, e)
        raise


def order_confirmation_processing_note() -> str | None:
    """Opcionális feldolgozás / szállítás szöveg (ORDER_CONFIRMATION_PROCESSING_NOTE)."""
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
    Sikeres Barion fizetés visszaigazolása — csak backend verify után hívandó.
    True = SMTP-n elküldve; False = nincs SMTP (dev napló).
    """
    line_blocks = []
    for name, qty, line_total in lines:
        line_blocks.append(f"  • {name} × {qty} — {line_total:,} Ft".replace(",", " "))
    items_text = "\n".join(line_blocks) if line_blocks else "  • (nincs tétel)"
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
