from __future__ import annotations

import pytest

from grafi_core.email.config import (
    can_send_via_smtp,
    is_mailpit_style_local,
    is_smtp_configured,
    smtp_brevo_from_misconfigured,
    smtp_config_diagnostic,
    smtp_config_issues,
    smtp_from_is_brevo_relay_login,
    smtp_mode,
    smtp_provider_label,
    smtp_resend_user_misconfigured,
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


def test_brevo_smtp_from_relay_login_misconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setenv("SMTP_USER", "ac902b001@smtp-brevo.com")
    monkeypatch.setenv("SMTP_PASSWORD", "key")
    monkeypatch.setenv("SMTP_FROM", "ac902b001@smtp-brevo.com")
    assert smtp_from_is_brevo_relay_login("ac902b001@smtp-brevo.com") is True
    assert smtp_brevo_from_misconfigured() is True


def test_resend_smtp_user_must_be_literal_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.resend.com")
    monkeypatch.setenv("SMTP_USER", "wrong@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "re_key")
    monkeypatch.setenv("SMTP_FROM", "onboarding@resend.dev")
    assert smtp_resend_user_misconfigured() is True
    monkeypatch.setenv("SMTP_USER", "resend")
    assert smtp_resend_user_misconfigured() is False


def test_smtp_config_diagnostic_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USER", "user@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("SMTP_FROM", "user@gmail.com")
    diag = smtp_config_diagnostic()
    assert diag["smtp_mode"] == "relay"
    assert diag["smtp_provider"] == "gmail"
    assert "gmail_from_with_non_gmail_host" not in smtp_config_issues() or smtp_provider_label() == "gmail"
