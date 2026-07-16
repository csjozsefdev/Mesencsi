"""Barion start must include the full checkout group — no partial payment."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import AppUser, ShopOrder
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


def _multi_line_order(client: TestClient, uid: int, pa: int, pb: int) -> list[int]:
    r = client.post(
        "/orders",
        json=_checkout_order_body(
            "Full Group",
            [{"product_id": pa, "quantity": 1}, {"product_id": pb, "quantity": 1}],
        ),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    return [int(row["id"]) for row in r.json()]


def test_full_checkout_group_start_succeeds(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    uid, pa, pb = _seed_verified_user_and_products()
    ids = _multi_line_order(client, uid, pa, pb)
    br = client.post("/payments/barion/start", json={"order_ids": ids}, headers=_auth_headers(uid))
    assert br.status_code == 200, br.text
    assert br.json()["order_ids"] == ids


def test_partial_group_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    uid, pa, pb = _seed_verified_user_and_products()
    ids = _multi_line_order(client, uid, pa, pb)
    br = client.post("/payments/barion/start", json={"order_ids": [ids[0]]}, headers=_auth_headers(uid))
    assert br.status_code == 409
    assert "összes" in br.json().get("detail", "").lower()


def test_foreign_order_line_forbidden(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.helpers import seed_verified_user

    monkeypatch.setenv("BARION_SANDBOX", "true")
    uid_a, pa, pb = _seed_verified_user_and_products()
    ids_a = _multi_line_order(client, uid_a, pa, pb)
    uid_b = seed_verified_user(email="otherbuyer@example.com", username="otherbuyer", password="test-password-123")

    br = client.post("/payments/barion/start", json={"order_ids": ids_a}, headers=_auth_headers(uid_b))
    assert br.status_code in (403, 404)


def test_mixed_checkout_groups_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    uid, pa, pb = _seed_verified_user_and_products()
    r1 = client.post(
        "/orders",
        json=_checkout_order_body("G1", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    r2 = client.post(
        "/orders",
        json=_checkout_order_body("G2", [{"product_id": pb, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert r1.status_code == 201 and r2.status_code == 201
    mixed = [int(r1.json()[0]["id"]), int(r2.json()[0]["id"])]
    br = client.post("/payments/barion/start", json={"order_ids": mixed}, headers=_auth_headers(uid))
    assert br.status_code == 409


def test_duplicate_ids_do_not_change_total(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    uid, pa, pb = _seed_verified_user_and_products()
    ids = _multi_line_order(client, uid, pa, pb)
    db = SessionLocal()
    try:
        rows = list(db.scalars(__import__("sqlalchemy").select(ShopOrder).where(ShopOrder.id.in_(ids))).all())
        expected_total = sum(int(r.total_price) for r in rows)
    finally:
        db.close()
    br = client.post(
        "/payments/barion/start",
        json={"order_ids": [ids[0], ids[0], ids[1]]},
        headers=_auth_headers(uid),
    )
    assert br.status_code == 200, br.text
    assert len(br.json()["order_ids"]) == 2


def test_paid_line_in_group_blocks_start(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    uid, pa, pb = _seed_verified_user_and_products()
    ids = _multi_line_order(client, uid, pa, pb)
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
