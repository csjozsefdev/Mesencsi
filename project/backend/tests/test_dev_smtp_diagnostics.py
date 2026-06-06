"""Local /dev/smtp-config diagnostic endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app


def test_dev_smtp_config_available_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("MESENCSI_PRODUCTION", raising=False)
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_USE_TLS", "0")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    with TestClient(app) as client:
        r = client.get("/dev/smtp-config")
    assert r.status_code == 200
    data = r.json()
    assert data["smtp_host"] == "127.0.0.1"
    assert data["smtp_provider"] == "mailpit"
    assert data["smtp_host_present"] is True
    assert data["smtp_port"] == "1025"
    assert data["smtp_password_present"] is False
    assert "smtp_password" not in data
    assert data["smtp_transport_mode"] == "plain"
    assert data["smtp_mode"] == "mailpit"
    assert data["smtp_fully_configured"] is False


def test_dev_smtp_config_gmail_fully_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("MESENCSI_PRODUCTION", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USE_TLS", "1")
    monkeypatch.setenv("SMTP_USER", "user@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret-app-pass")
    monkeypatch.setenv("SMTP_FROM", "user@gmail.com")
    with TestClient(app) as client:
        r = client.get("/dev/smtp-config")
    assert r.status_code == 200
    data = r.json()
    assert data["smtp_fully_configured"] is True
    assert data["smtp_mode"] == "relay"
    assert "smtp_password" not in data
    assert data["smtp_password_present"] is True


def test_dev_smtp_config_hidden_on_render(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("MESENCSI_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    with TestClient(app) as client:
        r = client.get("/dev/smtp-config")
    assert r.status_code == 404
