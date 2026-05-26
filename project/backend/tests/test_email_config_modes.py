"""SMTP mode: relay (Gmail/Render) vs optional Mailpit."""

from __future__ import annotations

import pytest

from email_config import (
    can_send_via_smtp,
    is_mailpit_style_local,
    is_smtp_configured,
    smtp_mode,
    smtp_config_diagnostic,
)


def test_gmail_relay_fully_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USE_TLS", "1")
    monkeypatch.setenv("SMTP_USER", "user@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password-here")
    monkeypatch.setenv("SMTP_FROM", "user@gmail.com")
    assert smtp_mode() == "relay"
    assert is_smtp_configured() is True
    assert can_send_via_smtp() is True
    assert is_mailpit_style_local() is False
    diag = smtp_config_diagnostic()
    assert diag["smtp_fully_configured"] is True
    assert diag["smtp_transport_mode"] == "starttls"


def test_mailpit_optional_not_fully_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_USE_TLS", "0")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setenv("SMTP_FROM", "noreply@localhost")
    assert smtp_mode() == "mailpit"
    assert is_smtp_configured() is False
    assert can_send_via_smtp() is True
    diag = smtp_config_diagnostic()
    assert diag["smtp_fully_configured"] is False
    assert diag["smtp_mailpit_style"] is True


def test_partial_gmail_missing_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@gmail.com")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setenv("SMTP_FROM", "user@gmail.com")
    assert smtp_mode() == "partial"
    assert can_send_via_smtp() is False
