"""SMTP policy: dev log fallback vs hosted require/raise; TLS transport modes."""

from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from email_config import smtp_transport_mode
from email_errors import EmailNotConfiguredError, EmailSendError
from email_outbound import public_base_url, send_email_verification, send_plain_email
from runtime_flags import auth_email_requires_working_smtp


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
    assert "LOCAL DEV AUTH EMAIL" in caplog.text


def test_hosted_missing_smtp_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    with pytest.raises(EmailNotConfiguredError):
        send_email_verification("user@example.com", "tok")


def test_production_smtp_send_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    with patch("email_outbound._smtp_session", side_effect=OSError("connection refused")):
        with pytest.raises(EmailSendError):
            send_email_verification("user@example.com", "tok-prod-fail")


def test_dev_log_auth_links_always_when_smtp_succeeds(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "false")
    monkeypatch.setenv("MESENCSI_DEV_LOG_AUTH_EMAIL_LINKS", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    caplog.set_level("WARNING")
    with patch("email_outbound.send_plain_email", return_value=True):
        assert send_email_verification("always-log@example.com", "tok-always") is True
    assert "LOCAL DEV AUTH EMAIL" in caplog.text
    assert "email_verify_token=tok-always" in caplog.text


def test_smtp_dev_debug_logs_auth_failure_stage(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "false")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USE_TLS", "1")
    monkeypatch.setenv("SMTP_USER", "qa.user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret-password")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    caplog.set_level("WARNING")

    mock_smtp = MagicMock()
    mock_smtp.starttls = MagicMock()
    mock_smtp.login = MagicMock(side_effect=smtplib.SMTPAuthenticationError(535, b"Auth failed"))
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    with patch("email_outbound.smtplib.SMTP", return_value=mock_smtp):
        with pytest.raises(EmailSendError):
            send_plain_email(to_email="dbg@example.com", subject="Sub", body="Body")

    assert "SMTP_DEV_DEBUG start" in caplog.text
    assert "smtp_user_masked=qa***@example.com" in caplog.text
    assert "tcp_connected=true" in caplog.text
    assert "starttls_ok=true" in caplog.text
    assert "failure_stage=during_login" in caplog.text
    assert "SMTPAuthenticationError" in caplog.text
    assert "secret-password" not in caplog.text


def test_smtp_dev_debug_disabled_in_production(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    caplog.set_level("WARNING")
    with patch("email_outbound._smtp_session", side_effect=OSError("connection refused")):
        with pytest.raises(EmailSendError):
            send_plain_email(to_email="a@b.com", subject="Sub", body="Body")
    assert "SMTP_DEV_DEBUG" not in caplog.text


def test_local_smtp_send_failure_logs_link_not_raises(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "false")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    caplog.set_level("WARNING")
    with patch("email_outbound._smtp_session", side_effect=OSError("connection refused")):
        assert send_email_verification("local-fail@example.com", "tok-local-fail") is False
    assert "LOCAL DEV AUTH EMAIL" in caplog.text
    assert "email_verify_token=tok-local-fail" in caplog.text


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


def test_local_partial_smtp_verification_logs_instead_of_raise(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("MESENCSI_PRODUCTION", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "u@gmail.com")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setenv("SMTP_FROM", "u@gmail.com")
    caplog.set_level("WARNING")
    assert send_email_verification("dev-partial@example.com", "tok-partial-dev") is False
    assert "LOCAL DEV AUTH EMAIL" in caplog.text
    assert "email_verify_token=tok-partial-dev" in caplog.text


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


def _clear_hosted_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("MESENCSI_PRODUCTION", "RENDER", "ENVIRONMENT", "ENV", "GRAFI_PRODUCTION"):
        monkeypatch.delenv(key, raising=False)


def test_auth_email_hosted_via_environment_var_without_mesencsi_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """A VPS setting only ENVIRONMENT=production (not MESENCSI_PRODUCTION) must still be treated as hosted."""
    _clear_hosted_signals(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert auth_email_requires_working_smtp() is True


def test_auth_email_hosted_via_render_flag_without_mesencsi_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_hosted_signals(monkeypatch)
    monkeypatch.setenv("RENDER", "true")
    assert auth_email_requires_working_smtp() is True


def test_auth_email_not_hosted_in_plain_local_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """Must not break local dev behavior: nothing set → not hosted."""
    _clear_hosted_signals(monkeypatch)
    assert auth_email_requires_working_smtp() is False


def test_register_hosted_via_environment_var_raises_and_does_not_leak_token(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Closes the leak: without this, ENVIRONMENT=production but no MESENCSI_PRODUCTION would
    silently swallow the failure AND print the raw verification link/token as a 'local dev' log."""
    _clear_hosted_signals(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    caplog.set_level("WARNING")
    with patch("email_outbound._smtp_session", side_effect=OSError("connection refused")):
        with pytest.raises(EmailSendError):
            send_email_verification("hosted-env@example.com", "tok-hosted-env-leak-check")
    assert "LOCAL DEV AUTH EMAIL" not in caplog.text
    assert "tok-hosted-env-leak-check" not in caplog.text
    assert "SMTP_DEV_DEBUG" not in caplog.text


def test_public_base_url_hosted_without_configured_url_uses_canonical_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never fall back to a localhost link in a hosted deployment."""
    _clear_hosted_signals(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("PUBLIC_SITE_URL", raising=False)
    monkeypatch.delenv("FRONTEND_BASE_URL", raising=False)
    url = public_base_url()
    assert "127.0.0.1" not in url
    assert url == "https://www.mesencsi.hu"


def test_public_base_url_hosted_prefers_configured_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_hosted_signals(monkeypatch)
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://www.mesencsi.hu/")
    assert public_base_url() == "https://www.mesencsi.hu"


def test_public_base_url_dev_fallback_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Must not break local dev behavior: unset in dev still falls back to 127.0.0.1."""
    _clear_hosted_signals(monkeypatch)
    monkeypatch.delenv("PUBLIC_SITE_URL", raising=False)
    monkeypatch.delenv("FRONTEND_BASE_URL", raising=False)
    assert public_base_url() == "http://127.0.0.1:8000"


def test_transactional_email_footer_uses_public_site_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://mesencsi.example")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USE_TLS", "1")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@mesencsi.example")
    mock_smtp = MagicMock()
    with patch("email_outbound.smtplib.SMTP", return_value=mock_smtp):
        assert send_plain_email(to_email="a@b.com", subject="Sub", body="Body") is True
    sent_message = mock_smtp.send_message.call_args.args[0]
    content = sent_message.get_content()
    assert "Mesencsi" in content
    assert "https://mesencsi.example/impresszum" in content
    assert "https://mesencsi.example/adatkezeles" in content
