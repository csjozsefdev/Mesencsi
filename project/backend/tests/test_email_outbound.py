"""SMTP policy: dev log fallback vs hosted require/raise; TLS transport modes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from email_config import smtp_transport_mode
from email_errors import EmailNotConfiguredError, EmailSendError
from email_outbound import send_email_verification, send_plain_email


def test_smtp_transport_mode_ports() -> None:
    assert smtp_transport_mode(port=465, use_starttls=True) == "ssl"
    assert smtp_transport_mode(port=465, use_starttls=False) == "ssl"
    assert smtp_transport_mode(port=587, use_starttls=True) == "starttls"
    assert smtp_transport_mode(port=1025, use_starttls=False) == "plain"


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
    with patch("email_outbound._smtp_session", side_effect=OSError("connection refused")):
        with pytest.raises(EmailSendError, match="SMTP delivery failed"):
            send_plain_email(to_email="a@b.com", subject="Test", body="Hi")


def test_local_partial_relay_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "u@gmail.com")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setenv("SMTP_FROM", "u@gmail.com")
    with pytest.raises(EmailSendError, match="incomplete"):
        send_plain_email(to_email="a@b.com", subject="Sub", body="Body")


def test_smtp_port_587_uses_starttls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USE_TLS", "1")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)
    with patch("email_outbound.smtplib.SMTP", return_value=mock_smtp) as smtp_ctor:
        assert send_plain_email(to_email="a@b.com", subject="Sub", body="Body") is True
    smtp_ctor.assert_called_once()
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once()


def test_smtp_port_465_uses_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)
    with patch("email_outbound.smtplib.SMTP_SSL", return_value=mock_smtp) as ssl_ctor:
        with patch("email_outbound.smtplib.SMTP") as plain_ctor:
            assert send_plain_email(to_email="a@b.com", subject="Sub", body="Body") is True
    ssl_ctor.assert_called_once()
    plain_ctor.assert_not_called()
    mock_smtp.login.assert_called_once()
