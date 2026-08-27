"""SMTP mode: relay (Gmail/Render) vs optional Mailpit."""

from __future__ import annotations

import pytest

from email_config import (
    can_send_via_smtp,
    is_mailpit_style_local,
    is_smtp_configured,
    smtp_brevo_from_misconfigured,
    smtp_from_is_brevo_relay_login,
    smtp_config_issues,
    smtp_provider_label,
    smtp_rackhost_user_misconfigured,
    smtp_resend_user_misconfigured,
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


def test_brevo_smtp_from_relay_login_misconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setenv("SMTP_USER", "ac902b001@smtp-brevo.com")
    monkeypatch.setenv("SMTP_PASSWORD", "key")
    monkeypatch.setenv("SMTP_FROM", "ac902b001@smtp-brevo.com")
    assert smtp_from_is_brevo_relay_login("ac902b001@smtp-brevo.com") is True
    assert smtp_brevo_from_misconfigured() is True
    diag = smtp_config_diagnostic()
    assert diag["smtp_brevo_from_misconfigured"] is True


def test_mailersend_gmail_from_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.mailersend.net")
    monkeypatch.setenv("SMTP_USER", "MS_test@mlsender.net")
    monkeypatch.setenv("SMTP_PASSWORD", "token")
    monkeypatch.setenv("SMTP_FROM", "user@gmail.com")
    assert smtp_provider_label() == "mailersend"
    assert "mailersend_from_should_be_verified_domain_not_gmail" in smtp_config_issues()


def test_resend_smtp_user_must_be_literal_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.resend.com")
    monkeypatch.setenv("SMTP_USER", "wrong@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "re_key")
    monkeypatch.setenv("SMTP_FROM", "onboarding@resend.dev")
    assert smtp_resend_user_misconfigured() is True
    monkeypatch.setenv("SMTP_USER", "resend")
    assert smtp_resend_user_misconfigured() is False


def test_brevo_verified_sender_from_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setenv("SMTP_USER", "ac902b001@smtp-brevo.com")
    monkeypatch.setenv("SMTP_PASSWORD", "key")
    monkeypatch.setenv("SMTP_FROM", "noreply@mesencsi.hu")
    assert smtp_brevo_from_misconfigured() is False


def test_rackhost_provider_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.rackhost.hu")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "no-reply@mesencsi.hu")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("SMTP_FROM", "no-reply@mesencsi.hu")
    assert smtp_provider_label() == "rackhost"
    assert smtp_rackhost_user_misconfigured() is False
    assert smtp_config_issues() == []
    diag = smtp_config_diagnostic()
    assert diag["smtp_transport_mode"] == "ssl"


def test_rackhost_user_must_be_full_email_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.rackhost.hu")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "no-reply")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("SMTP_FROM", "no-reply@mesencsi.hu")
    assert smtp_rackhost_user_misconfigured() is True
    assert "rackhost_user_must_be_full_email_address" in smtp_config_issues()


def test_rackhost_wrong_port_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.rackhost.hu")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "no-reply@mesencsi.hu")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("SMTP_FROM", "no-reply@mesencsi.hu")
    assert "rackhost_expected_port_465_implicit_ssl" in smtp_config_issues()


def test_partial_gmail_missing_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@gmail.com")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setenv("SMTP_FROM", "user@gmail.com")
    assert smtp_mode() == "partial"
    assert can_send_via_smtp() is False
