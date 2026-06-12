"""Owner-only destructive admin operations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from auth import create_admin_token
from database import SessionLocal
from db_models import AppUser, ShopOrder
from mesencsi import app
from password_utils import hash_password
from tests.test_checkout_bundle_integration import _checkout_order_body, _seed_verified_user_and_products


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _maint_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_admin_token(username='maint', role='maintenance')}"}


def _owner_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_admin_token(username='owner', role='owner')}"}


def _seed_shop_user() -> int:
    db = SessionLocal()
    try:
        user = AppUser(
            username="roletest",
            email="roletest@example.com",
            password_hash=hash_password("x"),
            is_active=True,
            email_verified_at=datetime.now(UTC),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def test_maintenance_cannot_verify_user(client: TestClient) -> None:
    uid = _seed_shop_user()
    r = client.patch(
        f"/admin/users/{uid}/verify",
        json={"email_verified": True},
        headers=_maint_headers(),
    )
    assert r.status_code == 403


def test_maintenance_cannot_ban_user(client: TestClient) -> None:
    uid = _seed_shop_user()
    r = client.patch(f"/admin/users/{uid}/ban", headers=_maint_headers())
    assert r.status_code == 403


def test_maintenance_cannot_delete_user(client: TestClient) -> None:
    uid = _seed_shop_user()
    r = client.delete(f"/admin/users/{uid}", headers=_maint_headers())
    assert r.status_code == 403


def test_maintenance_cannot_patch_payment_status(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    from tests.test_checkout_bundle_integration import _auth_headers

    cr = client.post(
        "/orders",
        json=_checkout_order_body("Role", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    oid = int(cr.json()[0]["id"])
    r = client.patch(
        f"/admin/orders/{oid}",
        json={"payment_status": "failed"},
        headers=_maint_headers(),
    )
    assert r.status_code == 403


def test_maintenance_can_patch_fulfillment_status(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    from tests.test_checkout_bundle_integration import _auth_headers

    cr = client.post(
        "/orders",
        json=_checkout_order_body("Role", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    oid = int(cr.json()[0]["id"])
    r = client.patch(
        f"/admin/orders/{oid}",
        json={"status": "processing"},
        headers=_maint_headers(),
    )
    assert r.status_code == 200, r.text


def test_maintenance_cannot_delete_order_line(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    from tests.test_checkout_bundle_integration import _auth_headers

    cr = client.post(
        "/orders",
        json=_checkout_order_body("Del", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    oid = int(cr.json()[0]["id"])
    r = client.delete(f"/admin/orders/{oid}", headers=_maint_headers())
    assert r.status_code == 403


def test_owner_can_verify_user(client: TestClient) -> None:
    from tests.helpers import seed_unverified_user

    uid = seed_unverified_user(email="owner-verify@example.com", username="ownerverify")
    r = client.patch(
        f"/admin/users/{uid}/verify",
        json={"email_verified": True},
        headers=_owner_headers(),
    )
    assert r.status_code == 200, r.text
