"""Cart must clear only after confirmed paid payment — not on order create or pending/cancel."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import UserCartItem
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


def _seed_cart(client: TestClient, uid: int, product_id: int) -> None:
    r = client.put(
        "/cart",
        headers=_auth_headers(uid),
        json={"items": [{"product_id": product_id, "quantity": 2}]},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1


def _cart_count(user_id: int) -> int:
    db = SessionLocal()
    try:
        return db.query(UserCartItem).filter(UserCartItem.user_id == user_id).count()
    finally:
        db.close()


def _create_order_and_start_barion(
    client: TestClient, uid: int, pa: int, *, payment_id: str = "cart-pay-test-001"
) -> tuple[int, str]:
    r = client.post(
        "/orders",
        json=_checkout_order_body("Cart Pay Teszt", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    oid = int(r.json()[0]["id"])
    with patch("routers.payments_barion.start_payment_request", return_value={"PaymentId": payment_id}):
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br.status_code == 200, br.text
    return oid, br.json()["payment_id"]


def test_create_order_does_not_clear_server_cart(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    _seed_cart(client, uid, pa)
    assert _cart_count(uid) == 1

    r = client.post(
        "/orders",
        json=_checkout_order_body("Buyer", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    assert _cart_count(uid) == 1

    rc = client.get("/cart", headers=_auth_headers(uid))
    assert rc.status_code == 200
    assert len(rc.json()) == 1
    assert rc.json()[0]["quantity"] == 2


def test_pending_barion_sync_does_not_clear_cart(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _barion_rest_env(monkeypatch)
    uid, pa, _pb = _seed_verified_user_and_products()
    _seed_cart(client, uid, pa)
    _oid, pid = _create_order_and_start_barion(client, uid, pa, payment_id="cart-pending-001")

    from routers.payments_barion import sync_orders_payment_status_from_barion

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Prepared"}):
        db = SessionLocal()
        try:
            shop, _ = sync_orders_payment_status_from_barion(db, pid)
            db.commit()
            assert shop == "pending"
        finally:
            db.close()

    assert _cart_count(uid) == 1


@pytest.mark.parametrize(
    "barion_status,expected_shop",
    [
        ("Failed", "failed"),
        ("Canceled", "cancelled"),
    ],
)
def test_non_success_barion_sync_does_not_clear_cart(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, barion_status: str, expected_shop: str
) -> None:
    _barion_rest_env(monkeypatch)
    uid, pa, _pb = _seed_verified_user_and_products()
    _seed_cart(client, uid, pa)
    _oid, pid = _create_order_and_start_barion(client, uid, pa, payment_id=f"cart-{expected_shop}-001")

    from routers.payments_barion import sync_orders_payment_status_from_barion

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": barion_status}):
        db = SessionLocal()
        try:
            shop, _ = sync_orders_payment_status_from_barion(db, pid)
            db.commit()
            assert shop == expected_shop
        finally:
            db.close()

    assert _cart_count(uid) == 1


def test_paid_barion_sync_clears_server_cart(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _barion_rest_env(monkeypatch)
    uid, pa, _pb = _seed_verified_user_and_products()
    _seed_cart(client, uid, pa)
    _oid, pid = _create_order_and_start_barion(client, uid, pa, payment_id="cart-paid-001")

    from routers.payments_barion import sync_orders_payment_status_from_barion

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Succeeded"}):
        db = SessionLocal()
        try:
            shop, _ = sync_orders_payment_status_from_barion(db, pid)
            db.commit()
            assert shop == "paid"
        finally:
            db.close()

    assert _cart_count(uid) == 0
    rc = client.get("/cart", headers=_auth_headers(uid))
    assert rc.status_code == 200
    assert rc.json() == []
