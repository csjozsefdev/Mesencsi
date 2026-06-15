"""Plain SMTP outbound mail — dev logs verification links when SMTP is optional."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import logging
import os
import smtplib
from contextlib import contextmanager
from email.message import EmailMessage
from grafi_core.email.transport import send_plain_email_via_smtp, smtp_credentials_from_env

from email_config import (
    can_send_via_smtp,
    is_mailpit_style_local,
    is_smtp_configured,
    smtp_config_diagnostic,
    smtp_from_is_brevo_relay_login,
    smtp_mode,
    smtp_port_from_env,
    smtp_required_for_outbound,
    smtp_transport_mode,
)
from env_loader import BACKEND_DIR
from email_errors import EmailNotConfiguredError, EmailSendError
from runtime_flags import auth_email_requires_working_smtp, dev_log_auth_email_links_always, mesencsi_production

logger = logging.getLogger(__name__)

RESEND_COOLDOWN_SEC = 120

_DEBUG_LOG_PATH = BACKEND_DIR.parent / "debug-624d64.log"


def _warn_brevo_smtp_from_not_deliverable(*, mail_from: str, to_email: str, subject: str) -> None:
    if not smtp_from_is_brevo_relay_login(mail_from):
        return
    logger.warning(
        "SMTP accepted by Brevo but SMTP_FROM=%r is the relay login (@smtp-brevo.com), not a verified "
        "sender — message to %s may never arrive. Set SMTP_FROM to a verified sender in Brevo "
        "(Senders, Domains & IPs) and check Brevo → Transactional → Email logs.",
        mail_from,
        _email_log_id(to_email),
    )
    if mesencsi_production():
        return
    # #region agent log
    try:
        import json
        import time

        payload = {
            "sessionId": "624d64",
            "runId": "brevo-from-check",
            "hypothesisId": "A",
            "location": "email_outbound.py:send_plain_email",
            "message": "brevo_smtp_from_is_relay_login",
            "data": {
                "mail_from_domain": mail_from.split("@")[-1] if "@" in mail_from else mail_from,
                "to_domain": to_email.split("@")[-1] if "@" in to_email else to_email,
                "subject": subject[:80],
                "smtp_send_ok": True,
            },
            "timestamp": int(time.time() * 1000),
        }
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass
    # #endregion


def _smtp_use_tls() -> bool:
    """STARTTLS on 587 when enabled; port 465 uses implicit SSL instead."""
    raw = (os.environ.get("SMTP_USE_TLS") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def public_base_url() -> str:
    """Public site URL used in email links (usually the storefront origin)."""
    return (
        os.environ.get("PUBLIC_SITE_URL")
        or os.environ.get("FRONTEND_BASE_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def _email_log_id(email: str) -> str:
    value = (email or "").strip()
    if "@" not in value:
        return "(invalid)"
    local, domain = value.rsplit("@", 1)
    prefix = local[:1] if local else "*"
    return f"{prefix}***@{domain.lower()}"


def _transactional_footer() -> str:
    base = public_base_url()
    return (
        "Mesencsi\n"
        f"Impresszum: {base}/impresszum\n"
        f"Adatkezelés: {base}/adatkezeles"
    )


def _with_transactional_footer(body: str) -> str:
    footer = _transactional_footer()
    if footer in body:
        return body
    return body.rstrip() + "\n\n---\n" + footer + "\n"


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


def _mask_smtp_user(user: str) -> str:
    """Partially mask SMTP_USER for dev logs (never log password)."""
    u = (user or "").strip()
    if not u:
        return "(empty)"
    if "@" in u:
        local, domain = u.split("@", 1)
        masked_local = (local[:2] + "***") if len(local) > 2 else ("*" * max(len(local), 1))
        return f"{masked_local}@{domain}"
    return (u[:2] + "***") if len(u) > 2 else "***"


def _smtp_dev_debug_enabled() -> bool:
    return not mesencsi_production()


def _log_smtp_dev_failure(
    *,
    failure_stage: str,
    exc: BaseException,
    host: str,
    port: int,
    use_tls: bool,
    transport_mode: str,
    smtp_user_masked: str,
    tcp_connected: bool,
    starttls_status: str,
    auth_status: str,
) -> None:
    if not _smtp_dev_debug_enabled():
        return
    logger.warning(
        "SMTP_DEV_DEBUG failure_stage=%s exception_type=%s exception_message=%r "
        "host=%s port=%s tls_enabled=%s transport_mode=%s smtp_user_masked=%s "
        "tcp_connected=%s starttls=%s smtp_auth=%s",
        failure_stage,
        type(exc).__name__,
        str(exc),
        host,
        port,
        use_tls,
        transport_mode,
        smtp_user_masked,
        tcp_connected,
        starttls_status,
        auth_status,
    )
    if failure_stage == "during_login" and _smtp_dev_debug_enabled():
        # #region agent log
        try:
            import json
            import time

            from email_config import smtp_config_issues, smtp_provider_label

            payload = {
                "sessionId": "624d64",
                "runId": "smtp-auth-fail",
                "hypothesisId": "A",
                "location": "email_outbound.py:_log_smtp_dev_failure",
                "message": "smtp_login_failed",
                "data": {
                    "failure_stage": failure_stage,
                    "exception_type": type(exc).__name__,
                    "host": host,
                    "port": port,
                    "smtp_provider": smtp_provider_label(),
                    "config_issues": smtp_config_issues(),
                },
                "timestamp": int(time.time() * 1000),
            }
            with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            pass
        # #endregion


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
    user_masked = _mask_smtp_user(user)
    if _smtp_dev_debug_enabled():
        logger.warning(
            "SMTP_DEV_DEBUG start host=%s port=%s tls_enabled=%s transport_mode=%s "
            "smtp_user_masked=%s password_configured=%s",
            host,
            port,
            use_tls,
            mode,
            user_masked,
            bool(password),
        )

    smtp: smtplib.SMTP | None = None
    failure_stage = "before_connect"
    tcp_connected = False
    starttls_status = "skipped" if mode == "plain" else ("n/a_implicit_ssl" if mode == "ssl" else "pending")
    auth_status = "skipped" if not user else "pending"

    try:
        logger.debug("SMTP connect mode=%s host=%s port=%s", mode, host, port)
        if mode == "ssl":
            smtp = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            smtp = smtplib.SMTP(host, port, timeout=30)
        tcp_connected = True
        if _smtp_dev_debug_enabled():
            logger.warning("SMTP_DEV_DEBUG tcp_connected=true host=%s port=%s", host, port)

        if mode == "starttls":
            failure_stage = "during_tls"
            smtp.starttls()
            starttls_status = "ok"
            if _smtp_dev_debug_enabled():
                logger.warning("SMTP_DEV_DEBUG starttls_ok=true")
        elif mode == "ssl":
            starttls_status = "n/a_implicit_ssl"
        else:
            starttls_status = "skipped_plain"

        if user:
            failure_stage = "during_login"
            if _smtp_dev_debug_enabled():
                logger.warning(
                    "SMTP_PROOF before_login host=%s port=%s smtp_user_masked=%s password_configured=%s",
                    host,
                    port,
                    user_masked,
                    bool(password),
                )
            try:
                smtp.login(user, password)
            except Exception as login_exc:
                if _smtp_dev_debug_enabled():
                    logger.warning(
                        "SMTP_PROOF after_login success=false exception_type=%s exception_message=%r",
                        type(login_exc).__name__,
                        str(login_exc),
                    )
                raise
            auth_status = "ok"
            if _smtp_dev_debug_enabled():
                logger.warning("SMTP_PROOF after_login success=true")
                logger.warning("SMTP_DEV_DEBUG smtp_auth_ok=true smtp_user_masked=%s", user_masked)
        else:
            auth_status = "skipped_no_user"

        failure_stage = "during_send"
        yield smtp
    except Exception as e:
        _log_smtp_dev_failure(
            failure_stage=failure_stage,
            exc=e,
            host=host,
            port=port,
            use_tls=use_tls,
            transport_mode=mode,
            smtp_user_masked=user_masked,
            tcp_connected=tcp_connected,
            starttls_status=starttls_status,
            auth_status=auth_status,
        )
        raise
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                smtp.close()


def _log_dev_verification_links(*, to_email: str, token: str) -> None:
    if mesencsi_production():
        return
    link = f"{public_base_url()}/?email_verify_token={token}"
    api_verify = f"{api_public_base_url()}/auth/verify-email?token={token}"
    logger.warning(
        "LOCAL DEV AUTH EMAIL — verification link (copy for QA) recipient=%s",
        _email_log_id(to_email),
    )
    logger.warning("  storefront: %s", link)
    logger.warning("  api:        %s", api_verify)


def _log_dev_password_reset_link(*, to_email: str, token: str) -> None:
    """Log reset link in local dev when SMTP did not send (never logged in production)."""
    if mesencsi_production():
        return
    link = f"{public_base_url()}/reset-password.html?token={token}"
    logger.warning(
        "LOCAL DEV AUTH EMAIL — password reset link (copy for QA) recipient=%s",
        _email_log_id(to_email),
    )
    logger.warning("  reset: %s", link)


def _raise_if_auth_smtp_required_but_missing() -> None:
    """Production shop auth mail: require full SMTP relay configuration."""
    if auth_email_requires_working_smtp() and not is_smtp_configured():
        logger.error(
            "SMTP is required (MESENCSI_PRODUCTION) but SMTP_HOST/SMTP_USER/SMTP_PASSWORD/SMTP_FROM are incomplete"
        )
        raise EmailNotConfiguredError(
            "SMTP is not configured for production. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM."
        )


def _attempt_outbound_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    on_dev_not_sent: Callable[[], None],
) -> bool:
    """
    Try SMTP send for shop verification/reset mail.

    MESENCSI_PRODUCTION=true: raise on misconfiguration or delivery failure.
    MESENCSI_PRODUCTION=false: log links via on_dev_not_sent and return False (no 503 to client).
    """
    if not auth_email_requires_working_smtp():
        smtp_host, _, _, _, _, _ = _smtp_settings()
        if not smtp_host or not can_send_via_smtp():
            on_dev_not_sent()
            return False
    else:
        _raise_if_auth_smtp_required_but_missing()

    try:
        sent = send_plain_email(to_email=to_email, subject=subject, body=body)
    except EmailNotConfiguredError:
        raise
    except EmailSendError as e:
        if auth_email_requires_working_smtp():
            raise
        logger.warning(
            "LOCAL DEV AUTH EMAIL — SMTP send failed (recipient=%s error=%s); link logged below",
            _email_log_id(to_email),
            e,
        )
        on_dev_not_sent()
        return False
    except Exception as e:
        if auth_email_requires_working_smtp():
            raise EmailSendError(f"Outbound email failed: {type(e).__name__}") from e
        logger.warning(
            "LOCAL DEV AUTH EMAIL — unexpected send error (recipient=%s error_type=%s)",
            _email_log_id(to_email),
            type(e).__name__,
            exc_info=True,
        )
        on_dev_not_sent()
        return False

    if sent:
        return True
    on_dev_not_sent()
    return False


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
    body = _with_transactional_footer(body)
    smtp_host, smtp_port, smtp_user, smtp_pass, mail_from, use_tls = _smtp_settings()
    transport = smtp_transport_mode(port=smtp_port, use_starttls=use_tls)

    _log_smtp_keys_loaded()
    logger.info(
        "Plain email send started — recipient=%s subject=%r smtp_configured=%s smtp_required=%s transport=%s host=%s port=%s",
        _email_log_id(to_email),
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
            "[email] SMTP_HOST not set — message not sent (dev log-only): recipient=%s subject=%r",
            _email_log_id(to_email),
            subject[:80],
        )
        logger.debug("[email] body preview:\n%s", body[:1500])
        return False

    if smtp_required_for_outbound() and not is_smtp_configured():
        _raise_if_smtp_required_but_missing()

    if not smtp_required_for_outbound() and smtp_host and not can_send_via_smtp():
        err = EmailSendError("SMTP relay config incomplete (missing USER, PASSWORD, or FROM)")
        if _smtp_dev_debug_enabled():
            _log_smtp_dev_failure(
                failure_stage="before_connect",
                exc=err,
                host=smtp_host,
                port=smtp_port,
                use_tls=use_tls,
                transport_mode=transport,
                smtp_user_masked=_mask_smtp_user(smtp_user),
                tcp_connected=False,
                starttls_status="not_attempted",
                auth_status="not_attempted",
            )
        logger.error(
            "SMTP partial config — for Gmail/Render set SMTP_HOST, SMTP_PORT=587, SMTP_USE_TLS=1, "
            "SMTP_USER, SMTP_PASSWORD (App Password), SMTP_FROM; or use Mailpit: "
            "SMTP_HOST=127.0.0.1 SMTP_PORT=1025 SMTP_USE_TLS=0 SMTP_FROM=noreply@localhost"
        )
        raise err

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_email
    msg.set_content(body)
    try:
        if _smtp_dev_debug_enabled():
            with _smtp_session(
                host=smtp_host,
                port=smtp_port,
                user=smtp_user,
                password=smtp_pass,
                use_tls=use_tls,
            ) as smtp:
                smtp.send_message(msg)
        else:
            send_plain_email_via_smtp(
                to_email=to_email,
                subject=subject,
                body=body,
                credentials=smtp_credentials_from_env(),
            )
    except EmailSendError:
        raise
    except Exception as e:
        logger.error(
            "SMTP send failed — recipient=%s subject=%r error_type=%s error=%s host=%s port=%s transport=%s",
            _email_log_id(to_email),
            subject[:80],
            type(e).__name__,
            e,
            smtp_host,
            smtp_port,
            transport,
            exc_info=True,
        )
        raise EmailSendError(f"SMTP delivery failed: {type(e).__name__}") from e

    if _smtp_dev_debug_enabled():
        logger.warning(
            "SMTP_DEV_DEBUG send_ok=true host=%s port=%s recipient=%s",
            smtp_host,
            smtp_port,
            _email_log_id(to_email),
        )
    logger.info("Plain email sent successfully — recipient=%s subject=%r", _email_log_id(to_email), subject[:80])
    _warn_brevo_smtp_from_not_deliverable(mail_from=mail_from, to_email=to_email, subject=subject)
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
    log_links = lambda: _log_dev_verification_links(to_email=to_email, token=token)
    sent = _attempt_outbound_email(
        to_email=to_email,
        subject=subject,
        body=body,
        on_dev_not_sent=log_links,
    )
    if sent:
        logger.info("Verification email sent successfully — recipient=%s", _email_log_id(to_email))
        if dev_log_auth_email_links_always():
            log_links()
    return sent


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
    products_grand_total_huf: int,
    shipping_method_label: str | None,
    shipping_package_label_hu: str | None = None,
    shipping_price_huf: int,
    shipping_address_plain: str | None = None,
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
    items_text = "\n".join(line_blocks) if line_blocks else "  • (nincs tétel)"
    products_fmt = f"{products_grand_total_huf:,} Ft".replace(",", " ")
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
        f"Termékek összesen: {products_fmt}",
    ]
    if shipping_method_label:
        body_parts.append(f"Szállítás: {shipping_method_label}")
        if shipping_package_label_hu:
            body_parts.append(f"Csomagméret: {shipping_package_label_hu}")
        if shipping_price_huf > 0:
            ship_fee = f"{shipping_price_huf:,} Ft".replace(",", " ")
            body_parts.append(f"Szállítási díj: {ship_fee}")
        elif shipping_method_label:
            body_parts.append("Szállítási díj: 0 Ft")
    if shipping_address_plain:
        body_parts.extend(["", "Szállítási cím:", shipping_address_plain])
    body_parts.append(f"Végösszeg: {grand_fmt}")
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
    log_links = lambda: _log_dev_password_reset_link(to_email=to_email, token=token)
    sent = _attempt_outbound_email(
        to_email=to_email,
        subject=subject,
        body=body,
        on_dev_not_sent=log_links,
    )
    if sent:
        logger.info("Password reset email sent successfully — recipient=%s", _email_log_id(to_email))
        if dev_log_auth_email_links_always():
            log_links()
    return sent
