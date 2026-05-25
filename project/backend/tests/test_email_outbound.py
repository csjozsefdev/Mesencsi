"""SMTP policy: dev log fallback vs hosted require/raise."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from email_errors import EmailNotConfiguredError, EmailSendError
from email_outbound import send_email_verification, send_plain_email


def test_dev_missing_smtp_logs_and_returns_false(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.delenv("MESENCSI_PRODUCTION", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    caplog.set_level("WARNING")
    assert send_email_verification("dev@example.com", "tok-dev") is False
    assert "DEV email fallback" in caplog.text


def test_hosted_missing_smtp_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    with pytest.raises(EmailNotConfiguredError):
        send_email_verification("user@example.com", "tok")


def test_hosted_smtp_send_failure_raises_email_send_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    with patch("email_outbound.smtplib.SMTP", side_effect=OSError("connection refused")):
        with pytest.raises(EmailSendError, match="SMTP delivery failed"):
            send_plain_email(to_email="a@b.com", subject="Test", body="Hi")


def test_smtp_success_returns_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)
    with patch("email_outbound.smtplib.SMTP", return_value=mock_smtp):
        assert send_plain_email(to_email="a@b.com", subject="Sub", body="Body") is True
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once()
