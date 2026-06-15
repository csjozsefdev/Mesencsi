"""POST /orders Idempotency-Key support."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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


def test_repeat_idempotency_key_returns_same_orders(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    body = _checkout_order_body("Idem Buyer", [{"product_id": pa, "quantity": 1}])
    headers = {**_auth_headers(uid), "Idempotency-Key": "checkout-abc-001"}
    r1 = client.post("/orders", json=body, headers=headers)
    r2 = client.post("/orders", json=body, headers=headers)
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text
    assert r1.json() == r2.json()


def test_invalid_idempotency_key_rejected(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    headers = {**_auth_headers(uid), "Idempotency-Key": "bad key!"}
    r = client.post(
        "/orders",
        json=_checkout_order_body("Buyer Alpha", [{"product_id": pa, "quantity": 1}]),
        headers=headers,
    )
    assert r.status_code == 422


def test_same_key_different_payload_conflict(client: TestClient) -> None:
    uid, pa, pb = _seed_verified_user_and_products()
    headers = {**_auth_headers(uid), "Idempotency-Key": "checkout-conflict-001"}
    r1 = client.post(
        "/orders",
        json=_checkout_order_body("Buyer Alpha", [{"product_id": pa, "quantity": 1}]),
        headers=headers,
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/orders",
        json=_checkout_order_body("Buyer Beta", [{"product_id": pb, "quantity": 1}]),
        headers=headers,
    )
    assert r2.status_code == 409
