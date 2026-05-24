"""Admin rendelés állapot: completed csak paid fizetés mellett."""

from __future__ import annotations

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


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer " + create_admin_token(username="owner", role="owner")}


def _create_pending_order(client: TestClient) -> int:
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Status Guard", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    row = r.json()[0]
    assert row["payment_status"] == "pending"
    return int(row["id"])


def test_admin_cannot_set_completed_when_payment_pending(client: TestClient) -> None:
    oid = _create_pending_order(client)
    pr = client.patch(
        f"/admin/orders/{oid}",
        json={"status": "completed"},
        headers=_admin_headers(),
    )
    assert pr.status_code == 409
    assert "paid" in pr.json().get("detail", "").lower() or "fizetett" in pr.json().get("detail", "")


def test_admin_can_set_completed_when_payment_paid(client: TestClient) -> None:
    oid = _create_pending_order(client)
    db = SessionLocal()
    try:
        row = db.get(ShopOrder, oid)
        assert row is not None
        row.payment_status = "paid"
        db.commit()
    finally:
        db.close()

    pr = client.patch(
        f"/admin/orders/{oid}",
        json={"status": "completed"},
        headers=_admin_headers(),
    )
    assert pr.status_code == 200, pr.text
    assert pr.json()["status"] == "completed"
    assert pr.json()["payment_status"] == "paid"


def test_admin_can_set_processing_on_pending_order(client: TestClient) -> None:
    oid = _create_pending_order(client)
    pr = client.patch(
        f"/admin/orders/{oid}",
        json={"status": "processing"},
        headers=_admin_headers(),
    )
    assert pr.status_code == 200, pr.text
    assert pr.json()["status"] == "processing"
    assert pr.json()["payment_status"] == "pending"
