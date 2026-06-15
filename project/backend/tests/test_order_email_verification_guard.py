"""POST /orders: csak email-verified user hozhat létre rendelést (összhangban GET /orders-szal)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from database import SessionLocal
from db_models import AppUser, Product, ShopOrder
from mesencsi import app
from password_utils import hash_password
from tests.test_checkout_bundle_integration import (
    _auth_headers,
    _checkout_order_body,
    _seed_verified_user_and_products,
)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _seed_unverified_user_and_product() -> tuple[int, int]:
    db = SessionLocal()
    try:
        u = AppUser(
            username="pytest_unverified",
            email="unverified@example.com",
            password_hash=hash_password("test-password-123"),
            is_active=True,
            is_banned=False,
            is_deleted=False,
            email_verified_at=None,
        )
        db.add(u)
        db.flush()
        p = Product(name="Book U", price=500, description="U")
        db.add(p)
        db.commit()
        db.refresh(u)
        db.refresh(p)
        return int(u.id), int(p.id)
    finally:
        db.close()


def _order_body(product_id: int) -> dict:
    return _checkout_order_body("Teszt Vásárló", [{"product_id": product_id, "quantity": 1}])


def test_unverified_user_cannot_create_order(client: TestClient) -> None:
    uid, pa = _seed_unverified_user_and_product()
    db = SessionLocal()
    try:
        before = int(db.scalar(select(func.count()).select_from(ShopOrder)) or 0)
    finally:
        db.close()

    r = client.post("/orders", json=_order_body(pa), headers=_auth_headers(uid))
    assert r.status_code == 403
    assert r.json().get("detail") == "A rendelés leadásához erősítsd meg az e-mail címed."

    db = SessionLocal()
    try:
        after = int(db.scalar(select(func.count()).select_from(ShopOrder)) or 0)
        assert after == before
    finally:
        db.close()


def test_verified_user_can_create_order(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post("/orders", json=_order_body(pa), headers=_auth_headers(uid))
    assert r.status_code == 201, r.text
    assert r.json()[0]["payment_status"] == "pending"


def test_unverified_user_cannot_list_orders_but_estimate_may_work(client: TestClient) -> None:
    uid, pa = _seed_unverified_user_and_product()
    list_r = client.get("/orders", headers=_auth_headers(uid))
    assert list_r.status_code == 403

    est_r = client.post(
        "/orders/estimate",
        json={"items": [{"product_id": pa, "quantity": 1}], "shipping_method": "personal_pickup"},
        headers=_auth_headers(uid),
    )
    assert est_r.status_code == 200
