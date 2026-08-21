"""BARION_PAYMENTS_ENABLED — decouples Barion production readiness from MESENCSI_PRODUCTION.

The webapp's own hardening (docs/redoc/openapi disabled, /dev endpoints gone, CORS +
HTTPS validation) must stay active under MESENCSI_PRODUCTION regardless of whether
Barion checkout itself is turned on. See startup_config.py and routers/payments_barion.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from openapi_docs import fastapi_openapi_kwargs
from startup_config import StartupConfigError, run_startup_config_validation
from tests.test_startup_config import _fill_minimal_production_env


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


# --- startup validation ------------------------------------------------------------


def test_production_barion_disabled_with_sandbox_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production app + Barion disabled + BARION_ENV=sandbox → app starts."""
    _fill_minimal_production_env(monkeypatch)
    monkeypatch.setenv("BARION_PAYMENTS_ENABLED", "false")
    monkeypatch.setenv("BARION_ENV", "sandbox")
    monkeypatch.delenv("BARION_IPN_SECRET", raising=False)
    run_startup_config_validation()


def test_production_barion_enabled_with_sandbox_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production app + Barion enabled + BARION_ENV=sandbox → app does not start."""
    _fill_minimal_production_env(monkeypatch)
    monkeypatch.setenv("BARION_PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("BARION_ENV", "sandbox")
    with pytest.raises(StartupConfigError) as exc:
        run_startup_config_validation()
    assert any("BARION_ENV" in i for i in exc.value.issues)


def test_production_barion_enabled_production_missing_secret_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production app + Barion enabled + BARION_ENV=production + missing BARION_IPN_SECRET → app does not start."""
    _fill_minimal_production_env(monkeypatch)
    monkeypatch.setenv("BARION_PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("BARION_ENV", "production")
    monkeypatch.delenv("BARION_IPN_SECRET", raising=False)
    with pytest.raises(StartupConfigError) as exc:
        run_startup_config_validation()
    assert any("BARION_IPN_SECRET" in i for i in exc.value.issues)


def test_production_barion_enabled_full_production_config_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production app + Barion enabled + full production Barion config → app starts."""
    _fill_minimal_production_env(monkeypatch)
    monkeypatch.setenv("BARION_PAYMENTS_ENABLED", "true")
    run_startup_config_validation()


def test_barion_payments_enabled_defaults_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backward compatibility: unset BARION_PAYMENTS_ENABLED behaves like true."""
    _fill_minimal_production_env(monkeypatch)
    monkeypatch.delenv("BARION_PAYMENTS_ENABLED", raising=False)
    run_startup_config_validation()


# --- request-time endpoint behaviour -------------------------------------------------


def test_barion_start_returns_503_when_payments_disabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.setenv("BARION_PAYMENTS_ENABLED", "false")
    r = client.post("/payments/barion/start", json={"order_ids": [1]})
    assert r.status_code == 503


def test_barion_callback_returns_503_when_payments_disabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.setenv("BARION_PAYMENTS_ENABLED", "false")
    r = client.post("/payments/barion/callback", json={"payment_id": "any-id-12345", "status": "Succeeded"})
    assert r.status_code == 503


def test_barion_webhook_alias_returns_503_when_payments_disabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.setenv("BARION_PAYMENTS_ENABLED", "false")
    r = client.post("/payments/barion/webhook", json={"payment_id": "any-id-12345", "status": "Succeeded"})
    assert r.status_code == 503


def test_barion_ipn_returns_503_when_payments_disabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.setenv("BARION_PAYMENTS_ENABLED", "false")
    monkeypatch.setenv("BARION_IPN_SECRET", "ipn-shared-secret-20")
    r = client.post(
        "/payments/barion/ipn?barion_ipn=ipn-shared-secret-20",
        json={"PaymentId": "any-id"},
    )
    assert r.status_code == 503


def test_barion_start_still_works_when_payments_enabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity check: disabling the flag doesn't leave it permanently 503 — enabled path is untouched
    (stub mode, no BARION_POS_KEY, so this reaches normal auth/validation instead of the toggle guard)."""
    monkeypatch.delenv("MESENCSI_PRODUCTION", raising=False)
    monkeypatch.delenv("BARION_PAYMENTS_ENABLED", raising=False)
    r = client.post("/payments/barion/start", json={"order_ids": [1]})
    assert r.status_code != 503


# --- webapp hardening stays decoupled from Barion -----------------------------------


def test_docs_disabled_in_production_regardless_of_barion_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """/docs, /redoc, /openapi.json gating is purely MESENCSI_PRODUCTION — proves no coupling to Barion."""
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.setenv("BARION_PAYMENTS_ENABLED", "false")
    kwargs = fastapi_openapi_kwargs()
    assert kwargs == {"docs_url": None, "redoc_url": None, "openapi_url": None}


def test_dev_smtp_config_still_hidden_in_production_with_barion_disabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.setenv("BARION_PAYMENTS_ENABLED", "false")
    r = client.get("/dev/smtp-config")
    assert r.status_code == 404
