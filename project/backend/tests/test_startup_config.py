"""Startup config validator: prod fatal, dev warning only."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from startup_config import StartupConfigError, run_startup_config_validation


def _fill_minimal_production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.setenv("USER_JWT_SECRET", "u" * 40)
    monkeypatch.setenv("ADMIN_JWT_SECRET", "a" * 40)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://shop.example.com")
    monkeypatch.setenv("POSTGRES_USER", "mesencsi")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_DB", "mesencsi")
    monkeypatch.delenv("MESENCSI_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("BARION_POS_KEY", "pos-key-value-16chars-min")
    monkeypatch.setenv("BARION_PAYEE_EMAIL", "payee@example.com")
    monkeypatch.setenv("BARION_IPN_SECRET", "ipn-secret-value-16b-min")
    monkeypatch.setenv("BARION_ENV", "production")
    monkeypatch.setenv("BARION_BACKEND_PUBLIC_URL", "https://api.example.com")
    monkeypatch.setenv("BARION_RETURN_URL", "https://api.example.com/payments/barion/return")
    monkeypatch.setenv("BARION_CALLBACK_URL", "https://api.example.com/payments/barion/ipn")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-pass")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")


def test_production_missing_admin_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _fill_minimal_production_env(monkeypatch)
    monkeypatch.delenv("ADMIN_JWT_SECRET", raising=False)
    with pytest.raises(StartupConfigError) as exc:
        run_startup_config_validation()
    assert any("ADMIN_JWT_SECRET" in i for i in exc.value.issues)


def test_production_valid_config_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _fill_minimal_production_env(monkeypatch)
    run_startup_config_validation()


def test_production_with_test_database_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _fill_minimal_production_env(monkeypatch)
    monkeypatch.setenv("MESENCSI_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    with pytest.raises(StartupConfigError) as exc:
        run_startup_config_validation()
    assert any("MESENCSI_TEST_DATABASE_URL" in i for i in exc.value.issues)


def test_dev_with_test_database_url_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MESENCSI_PRODUCTION", raising=False)
    monkeypatch.setenv("MESENCSI_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    run_startup_config_validation()


def test_dev_missing_secrets_only_warns(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.delenv("MESENCSI_PRODUCTION", raising=False)
    monkeypatch.delenv("ADMIN_JWT_SECRET", raising=False)
    monkeypatch.delenv("USER_JWT_SECRET", raising=False)
    monkeypatch.setenv("MESENCSI_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    caplog.set_level("WARNING")
    run_startup_config_validation()
    assert "startup_config_warning" in caplog.text or "startup_config_summary" in caplog.text


def test_app_starts_in_dev_with_test_db() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200


def test_app_lifespan_fails_in_production_with_bad_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _fill_minimal_production_env(monkeypatch)
    monkeypatch.delenv("BARION_IPN_SECRET", raising=False)
    with pytest.raises(StartupConfigError):
        with TestClient(app):
            pass


def test_render_hosted_missing_smtp_raises_without_production_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MESENCSI_PRODUCTION", raising=False)
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("USER_JWT_SECRET", "u" * 40)
    monkeypatch.setenv("ADMIN_JWT_SECRET", "a" * 40)
    monkeypatch.setenv("MESENCSI_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with pytest.raises(StartupConfigError) as exc:
        run_startup_config_validation()
    assert any("SMTP" in i for i in exc.value.issues)
