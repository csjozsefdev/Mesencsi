"""Guest checkout: public estimate/order, Barion stub, email, order linking."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from database import SessionLocal
from db_models import AppUser, Product, ShopOrder
from guest_checkout_tokens import guest_checkout_token_header_name
from mesencsi import app
from password_utils import hash_password
from shipping_address import sample_valid_shipping_json
from tests.test_checkout_bundle_integration import (
    _auth_headers,
    _checkout_order_body,
    _seed_verified_user_and_products,
)
from user_email_verify import assign_verification_to_user, issue_verification_token
from user_tokens import issue_user_access_token


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _guest_csrf_headers(client: TestClient) -> dict[str, str]:
    r = client.get("/auth/csrf")
    assert r.status_code == 200, r.text
    csrf = client.cookies.get("mesencsi_csrf")
    assert csrf
    return {"X-CSRF-Token": csrf}


def _guest_order_body(email: str, product_id: int, **extra: object) -> dict:
    body = _checkout_order_body(
        "Guest Buyer",
        [{"product_id": product_id, "quantity": 1}],
        customer_email=email,
    )
    body.update(extra)
    return body


def _seed_product() -> int:
    db = SessionLocal()
    try:
        p = Product(name="Guest Book", price=1500, description="G")
        db.add(p)
        db.commit()
        db.refresh(p)
        return int(p.id)
    finally:
        db.close()


def test_guest_can_estimate_without_auth(client: TestClient) -> None:
    pa = _seed_product()
    r = client.post(
        "/orders/estimate",
        json={"items": [{"product_id": pa, "quantity": 2}], "shipping_method": "personal_pickup"},
        headers=_guest_csrf_headers(client),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["grand_final"] == 3000


def test_guest_cannot_use_coupon_on_estimate(client: TestClient) -> None:
    pa = _seed_product()
    r = client.post(
        "/orders/estimate",
        json={
            "items": [{"product_id": pa, "quantity": 1}],
            "shipping_method": "personal_pickup",
            "coupon_code": "SAVE10",
        },
        headers=_guest_csrf_headers(client),
    )
    assert r.status_code == 403


def test_guest_order_created_with_null_user_id(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    pa = _seed_product()
    email = "guest.buyer@example.com"
    r = client.post(
        "/orders",
        json=_guest_order_body(email, pa),
        headers=_guest_csrf_headers(client),
    )
    assert r.status_code == 201, r.text
    token = r.headers.get(guest_checkout_token_header_name())
    assert token
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["user_id"] is None
    assert rows[0]["customer_email"] == email

    order_ids = [int(x["id"]) for x in rows]
    br = client.post(
        "/payments/barion/start",
        json={"order_ids": order_ids},
        headers={**_guest_csrf_headers(client), guest_checkout_token_header_name(): token},
    )
    assert br.status_code == 200, br.text
    assert br.json().get("redirect_url")

    pid = br.json()["payment_id"]
    cb = client.post(
        "/payments/barion/callback",
        json={"payment_id": pid, "status": "Succeeded"},
    )
    assert cb.status_code == 204

    db = SessionLocal()
    try:
        row = db.get(ShopOrder, order_ids[0])
        assert row is not None
        assert row.user_id is None
        assert row.payment_status == "paid"
    finally:
        db.close()


def test_guest_payment_state_with_token(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    pa = _seed_product()
    email = "guest.state@example.com"
    r = client.post(
        "/orders",
        json=_guest_order_body(email, pa),
        headers=_guest_csrf_headers(client),
    )
    token = r.headers[guest_checkout_token_header_name()]
    order_ids = [int(x["id"]) for x in r.json()]
    br = client.post(
        "/payments/barion/start",
        json={"order_ids": order_ids},
        headers={**_guest_csrf_headers(client), guest_checkout_token_header_name(): token},
    )
    pid = br.json()["payment_id"]
    client.post("/payments/barion/callback", json={"payment_id": pid, "status": "Succeeded"})

    st = client.get(
        f"/payments/barion/payment/{pid}/state",
        headers={guest_checkout_token_header_name(): token},
    )
    assert st.status_code == 200, st.text
    assert st.json()["payment_status"] == "paid"


def test_guest_barion_start_without_token_rejected(client: TestClient) -> None:
    pa = _seed_product()
    r = client.post(
        "/orders",
        json=_guest_order_body("no.token@example.com", pa),
        headers=_guest_csrf_headers(client),
    )
    order_ids = [int(x["id"]) for x in r.json()]
    br = client.post(
        "/payments/barion/start",
        json={"order_ids": order_ids},
        headers=_guest_csrf_headers(client),
    )
    assert br.status_code == 401


def test_authenticated_checkout_still_works(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Auth Buyer", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    assert r.json()[0]["user_id"] == uid
    assert guest_checkout_token_header_name() not in r.headers

    br = client.post(
        "/payments/barion/start",
        json={"order_ids": [int(r.json()[0]["id"])]},
        headers=_auth_headers(uid),
    )
    assert br.status_code == 200


def test_guest_order_requires_email(client: TestClient) -> None:
    pa = _seed_product()
    body = _checkout_order_body("Guest", [{"product_id": pa, "quantity": 1}])
    r = client.post("/orders", json=body, headers=_guest_csrf_headers(client))
    assert r.status_code == 422


def test_verified_registration_links_guest_orders(client: TestClient) -> None:
    pa = _seed_product()
    guest_email = "linkme@example.com"
    db = SessionLocal()
    try:
        r = client.post(
            "/orders",
            json=_guest_order_body(guest_email, pa),
            headers=_guest_csrf_headers(client),
        )
        order_id = int(r.json()[0]["id"])
        row = db.get(ShopOrder, order_id)
        assert row is not None
        row.payment_status = "paid"
        db.commit()

        token_plain = issue_verification_token()
        user = AppUser(
            username="linkme",
            email=guest_email,
            password_hash=hash_password("test-password-123"),
            is_active=True,
            is_banned=False,
            is_deleted=False,
        )
        assign_verification_to_user(db, user, token_plain)
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    vr = client.get(f"/auth/verify-email?token={token_plain}")
    assert vr.status_code == 200, vr.text

    db = SessionLocal()
    try:
        linked = db.get(ShopOrder, order_id)
        assert linked is not None
        assert linked.user_id is not None
        user_row = db.get(AppUser, linked.user_id)
        assert user_row is not None
        assert user_row.email == guest_email
    finally:
        db.close()


def test_unverified_user_still_blocked_from_order(client: TestClient) -> None:
    db = SessionLocal()
    try:
        u = AppUser(
            username="unverified_guest_block",
            email="unverified_guest_block@example.com",
            password_hash=hash_password("test-password-123"),
            is_active=True,
            is_banned=False,
            is_deleted=False,
            email_verified_at=None,
        )
        db.add(u)
        db.flush()
        p = Product(name="X", price=100, description="x")
        db.add(p)
        db.commit()
        db.refresh(u)
        db.refresh(p)
        uid, pid = int(u.id), int(p.id)
    finally:
        db.close()

    r = client.post(
        "/orders",
        json=_checkout_order_body("Unverified Buyer", [{"product_id": pid, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 403, r.text


def test_guest_cannot_list_orders(client: TestClient) -> None:
    r = client.get("/orders")
    assert r.status_code == 401
