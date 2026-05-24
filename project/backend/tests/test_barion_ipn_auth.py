"""Barion IPN: közös titok / fejléc validáció (CallbackUrl query + GetPaymentState mint hivatalos ellenőrzés)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_barion_ipn_rejects_when_secret_set_but_missing_from_request(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_IPN_SECRET", "ipn-shared-secret-20")
    r = client.post("/payments/barion/ipn", json={"PaymentId": "test-payment-01"})
    assert r.status_code == 403


def test_barion_ipn_accepts_matching_query_param(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_IPN_SECRET", "ipn-shared-secret-20")
    r = client.post(
        "/payments/barion/ipn?barion_ipn=ipn-shared-secret-20",
        json={"PaymentId": "any-id-no-pos-key"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data.get("sync") in ("ok", "skipped")


def test_barion_ipn_accepts_x_barion_ipn_secret_header(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_IPN_SECRET", "ipn-shared-secret-20")
    r = client.post(
        "/payments/barion/ipn",
        json={"PaymentId": "x"},
        headers={"X-Barion-Ipn-Secret": "ipn-shared-secret-20"},
    )
    assert r.status_code == 200


def test_barion_ipn_accepts_authorization_bearer(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_IPN_SECRET", "ipn-shared-secret-20")
    r = client.post(
        "/payments/barion/ipn",
        json={"PaymentId": "x"},
        headers={"Authorization": "Bearer ipn-shared-secret-20"},
    )
    assert r.status_code == 200


def test_barion_ipn_forbidden_in_production_without_secret(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.delenv("BARION_IPN_SECRET", raising=False)
    r = client.post("/payments/barion/ipn", json={"PaymentId": "x"})
    assert r.status_code == 403


def test_barion_ipn_reports_sync_failed_on_sync_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_IPN_SECRET", "ipn-shared-secret-20")
    monkeypatch.setenv("BARION_POS_KEY", "test-pos-key-16chars-xx")
    monkeypatch.setenv("BARION_PAYEE_EMAIL", "payee@example.com")

    def _sync_boom(db, pid: str) -> None:
        raise RuntimeError("sync boom")

    monkeypatch.setattr(
        "routers.payments_barion.sync_orders_payment_status_from_barion",
        _sync_boom,
    )
    r = client.post(
        "/payments/barion/ipn?barion_ipn=ipn-shared-secret-20",
        json={"PaymentId": "pay-sync-fail-01"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data.get("sync") == "failed"
    assert data.get("sync_failed") is True


def test_attach_barion_ipn_query_appends_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_IPN_SECRET", "abc123")
    from barion_api import attach_barion_ipn_query

    u = attach_barion_ipn_query("https://shop.example/api/payments/barion/ipn")
    assert "barion_ipn=abc123" in u
    u2 = attach_barion_ipn_query("https://shop.example/cb?foo=1")
    assert "foo=1" in u2 and "barion_ipn=abc123" in u2
