"""Tests for grafi_core SMTP transport."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from grafi_core.email.errors import EmailNotConfiguredError, EmailSendError
from grafi_core.email.transport import SmtpCredentials, send_plain_email_via_smtp, smtp_credentials_from_env


def test_smtp_credentials_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "mail.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    creds = smtp_credentials_from_env()
    assert creds.host == "mail.example.com"
    assert creds.port == 587
    assert creds.mail_from == "noreply@example.com"
    assert creds.use_tls is True


def test_send_plain_email_requires_host() -> None:
    creds = SmtpCredentials(host="", port=587, user="", password="", mail_from="a@b.c", use_tls=True)
    with pytest.raises(EmailNotConfiguredError):
        send_plain_email_via_smtp(to_email="to@example.com", subject="Hi", body="Body", credentials=creds)


def test_send_plain_email_success() -> None:
    creds = SmtpCredentials(host="localhost", port=1025, user="", password="", mail_from="a@b.c", use_tls=False)
    smtp = MagicMock()
    with patch("grafi_core.email.transport.smtp_session") as mock_session:
        mock_session.return_value.__enter__.return_value = smtp
        send_plain_email_via_smtp(
            to_email="to@example.com",
            subject="Subject",
            body="Hello",
            credentials=creds,
        )
    smtp.send_message.assert_called_once()


def test_send_plain_email_wraps_smtp_errors() -> None:
    creds = SmtpCredentials(host="localhost", port=1025, user="", password="", mail_from="a@b.c", use_tls=False)
    with patch("grafi_core.email.transport.smtp_session", side_effect=OSError("connection refused")):
        with pytest.raises(EmailSendError, match="SMTP delivery failed"):
            send_plain_email_via_smtp(
                to_email="to@example.com",
                subject="Subject",
                body="Hello",
                credentials=creds,
            )
