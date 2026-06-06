"""SMTP transport — send plain-text email via smtplib."""

from __future__ import annotations

import logging
import os
import smtplib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from email.message import EmailMessage

from grafi_core.email.config import smtp_port_from_env, smtp_transport_mode
from grafi_core.email.errors import EmailNotConfiguredError, EmailSendError

logger = logging.getLogger("grafi.email.transport")


@dataclass(frozen=True)
class SmtpCredentials:
    host: str
    port: int
    user: str
    password: str
    mail_from: str
    use_tls: bool


def smtp_credentials_from_env() -> SmtpCredentials:
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    mail_from = (os.environ.get("SMTP_FROM") or user or "noreply@localhost").strip()
    raw_tls = (os.environ.get("SMTP_USE_TLS") or "1").strip().lower()
    use_tls = raw_tls not in ("0", "false", "no", "off")
    return SmtpCredentials(
        host=host,
        port=smtp_port_from_env(),
        user=user,
        password=password,
        mail_from=mail_from,
        use_tls=use_tls,
    )


@contextmanager
def smtp_session(credentials: SmtpCredentials) -> Iterator[smtplib.SMTP]:
    mode = smtp_transport_mode(port=credentials.port, use_starttls=credentials.use_tls)
    smtp: smtplib.SMTP | None = None
    try:
        if mode == "ssl":
            smtp = smtplib.SMTP_SSL(credentials.host, credentials.port, timeout=30)
        else:
            smtp = smtplib.SMTP(credentials.host, credentials.port, timeout=30)
        if mode == "starttls":
            smtp.starttls()
        if credentials.user:
            smtp.login(credentials.user, credentials.password)
        yield smtp
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                smtp.close()


def send_plain_email_via_smtp(
    *,
    to_email: str,
    subject: str,
    body: str,
    credentials: SmtpCredentials | None = None,
    on_send_error: Callable[[Exception], None] | None = None,
) -> None:
    creds = credentials or smtp_credentials_from_env()
    if not creds.host:
        raise EmailNotConfiguredError("SMTP_HOST is not set")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = creds.mail_from
    message["To"] = to_email.strip()
    message.set_content(body)
    try:
        with smtp_session(creds) as smtp:
            smtp.send_message(message)
    except EmailSendError:
        raise
    except Exception as exc:
        if on_send_error:
            on_send_error(exc)
        raise EmailSendError(f"SMTP delivery failed: {type(exc).__name__}") from exc
