"""Barion verify: GetPaymentState szinkron, duplicate IPN, admin paid tiltás."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth import create_admin_token
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


def _barion_rest_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_POS_KEY", "test-pos-key-16chars")
    monkeypatch.setenv("BARION_PAYEE_EMAIL", "payee@example.com")


def _start_barion_payment(client: TestClient, uid: int, oid: int, *, payment_id: str = "test-barion-pay-001") -> str:
    with patch("routers.payments_barion.start_payment_request", return_value={"PaymentId": payment_id}):
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br.status_code == 200, br.text
    return br.json()["payment_id"]


def test_sync_from_barion_sets_paid_and_idempotent_on_duplicate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _barion_rest_env(monkeypatch)
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Verify Teszt", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    oid = int(r.json()[0]["id"])
    pid = _start_barion_payment(client, uid, oid)

    fake_state = {"Status": "Succeeded"}
    with patch("routers.payments_barion.get_payment_state", return_value=fake_state):
        monkeypatch.setenv("BARION_IPN_SECRET", "ipn-secret-test-16b")
        assert client.post(
            "/payments/barion/ipn?barion_ipn=ipn-secret-test-16b",
            json={"PaymentId": pid},
        ).status_code == 200
        assert client.post(
            "/payments/barion/ipn?barion_ipn=ipn-secret-test-16b",
            json={"PaymentId": pid},
        ).status_code == 200

    db = SessionLocal()
    try:
        row = db.get(ShopOrder, oid)
        assert row is not None
        assert row.payment_status == "paid"
    finally:
        db.close()

    with patch("routers.payments_barion.get_payment_state", return_value=fake_state) as mock_gs:
        monkeypatch.setenv("BARION_IPN_SECRET", "ipn-secret-test-16b")
        client.post(
            "/payments/barion/ipn?barion_ipn=ipn-secret-test-16b",
            json={"PaymentId": pid},
        )
        assert mock_gs.call_count == 1


def test_sync_maps_failed_and_cancelled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _barion_rest_env(monkeypatch)
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Státusz Teszt", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    oid = int(r.json()[0]["id"])
    pid = _start_barion_payment(client, uid, oid, payment_id="test-barion-pay-002")

    from routers.payments_barion import sync_orders_payment_status_from_barion

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Failed"}):
        db = SessionLocal()
        try:
            shop, _ = sync_orders_payment_status_from_barion(db, pid)
            assert shop == "failed"
            assert db.get(ShopOrder, oid).payment_status == "failed"
        finally:
            db.close()

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Canceled"}):
        db = SessionLocal()
        try:
            shop, _ = sync_orders_payment_status_from_barion(db, pid)
            assert shop == "cancelled"
            assert db.get(ShopOrder, oid).payment_status == "cancelled"
        finally:
            db.close()


def test_admin_cannot_set_paid(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Admin Pay", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    oid = int(r.json()[0]["id"])
    ah = {"Authorization": "Bearer " + create_admin_token(username="owner", role="owner")}
    pr = client.patch(f"/admin/orders/{oid}", json={"payment_status": "paid"}, headers=ah)
    assert pr.status_code == 400
    assert "Fizetve" in pr.json().get("detail", "")


def test_return_redirect_syncs_via_get_payment_state(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _barion_rest_env(monkeypatch)
    monkeypatch.setenv("BARION_FRONTEND_LANDING_URL", "http://shop.test")
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Return Teszt", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    oid = int(r.json()[0]["id"])
    pid = _start_barion_payment(client, uid, oid, payment_id="test-barion-pay-003")

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Succeeded"}):
        resp = client.get(f"/payments/barion/return?paymentId={pid}", follow_redirects=False)
    assert resp.status_code == 302
    loc = resp.headers.get("location", "")
    assert "payment=barion" in loc and "result=paid" in loc and f"pid={pid}" in loc
