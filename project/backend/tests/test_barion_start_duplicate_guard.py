"""POST /payments/barion/start: duplicate guard — pending resume, paid tiltás, failed retry."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import ShopOrder
from mesencsi import app
from tests.test_checkout_bundle_integration import (
    _auth_headers,
    _checkout_order_body,
    _seed_verified_user_and_products,
)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _create_order(client: TestClient, uid: int, pa: int) -> list[int]:
    r = client.post(
        "/orders",
        json=_checkout_order_body("Dup Guard", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    return [int(r.json()[0]["id"])]


def test_first_barion_start_succeeds(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    uid, pa, _pb = _seed_verified_user_and_products()
    ids = _create_order(client, uid, pa)
    br = client.post("/payments/barion/start", json={"order_ids": ids}, headers=_auth_headers(uid))
    assert br.status_code == 200, br.text
    assert br.json()["payment_id"].startswith("preview-")
    assert br.json().get("resumed_existing") is False


def test_second_start_resumes_same_payment_id_without_new_barion_call(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BARION_POS_KEY", "test-pos-key-16chars")
    monkeypatch.setenv("BARION_PAYEE_EMAIL", "payee@example.com")
    uid, pa, _pb = _seed_verified_user_and_products()
    ids = _create_order(client, uid, pa)

    with patch("routers.payments_barion.start_payment_request", return_value={"PaymentId": "dup-pay-001"}) as mock_start:
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            r1 = client.post("/payments/barion/start", json={"order_ids": ids}, headers=_auth_headers(uid))
            assert r1.status_code == 200
            pid1 = r1.json()["payment_id"]
            assert mock_start.call_count == 1

            r2 = client.post("/payments/barion/start", json={"order_ids": ids}, headers=_auth_headers(uid))
            assert r2.status_code == 200
            assert r2.json()["payment_id"] == pid1
            assert r2.json().get("resumed_existing") is True
            assert mock_start.call_count == 1

    db = SessionLocal()
    try:
        row = db.get(ShopOrder, ids[0])
        assert row is not None
        assert row.barion_payment_id == pid1
    finally:
        db.close()


def test_paid_order_cannot_start_payment(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    uid, pa, _pb = _seed_verified_user_and_products()
    ids = _create_order(client, uid, pa)
    client.post("/payments/barion/start", json={"order_ids": ids}, headers=_auth_headers(uid))

    db = SessionLocal()
    try:
        row = db.get(ShopOrder, ids[0])
        assert row is not None
        row.payment_status = "paid"
        db.commit()
    finally:
        db.close()

    br = client.post("/payments/barion/start", json={"order_ids": ids}, headers=_auth_headers(uid))
    assert br.status_code == 409
    assert "fizetett" in br.json().get("detail", "").lower() or "paid" in br.json().get("detail", "").lower()


def test_failed_payment_allows_new_start_with_new_payment_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BARION_POS_KEY", "test-pos-key-16chars")
    monkeypatch.setenv("BARION_PAYEE_EMAIL", "payee@example.com")
    uid, pa, _pb = _seed_verified_user_and_products()
    ids = _create_order(client, uid, pa)

    with patch("routers.payments_barion.start_payment_request", side_effect=[{"PaymentId": "old-fail-01"}, {"PaymentId": "new-retry-02"}]):
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            client.post("/payments/barion/start", json={"order_ids": ids}, headers=_auth_headers(uid))
            db = SessionLocal()
            try:
                row = db.get(ShopOrder, ids[0])
                assert row is not None
                row.payment_status = "failed"
                db.commit()
            finally:
                db.close()

            br = client.post("/payments/barion/start", json={"order_ids": ids}, headers=_auth_headers(uid))
            assert br.status_code == 200
            assert br.json()["payment_id"] == "new-retry-02"
            assert br.json().get("resumed_existing") is False

    db = SessionLocal()
    try:
        row = db.get(ShopOrder, ids[0])
        assert row.barion_payment_id == "new-retry-02"
        assert row.payment_status == "pending"
    finally:
        db.close()
