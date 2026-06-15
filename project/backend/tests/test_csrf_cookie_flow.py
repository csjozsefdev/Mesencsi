"""CSRF protection is enforced for cookie-auth browser flows."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import AppUser, Product
from mesencsi import app
from password_utils import hash_password
from shipping_address import sample_valid_shipping_json


def _seed_user_and_product() -> tuple[str, str, int]:
    db = SessionLocal()
    try:
        email = "csrfbuyer@example.com"
        password = "test-password-123"
        u = AppUser(
            username="csrfbuyer",
            email=email,
            password_hash=hash_password(password),
            is_active=True,
            is_banned=False,
            is_deleted=False,
            email_verified_at=datetime.now(UTC),
        )
        db.add(u)
        db.flush()
        p = Product(name="CSRF Book", price=1500, description="d")
        db.add(p)
        db.commit()
        db.refresh(p)
        return email, password, int(p.id)
    finally:
        db.close()


def test_cookie_authenticated_post_requires_csrf_header() -> None:
    email, password, product_id = _seed_user_and_product()
    client = TestClient(app)

    lr = client.post("/auth/login", json={"email": email, "password": password})
    assert lr.status_code == 200, lr.text
    assert client.cookies.get("mesencsi_user_token")
    csrf_cookie = client.cookies.get("mesencsi_csrf")
    assert csrf_cookie

    # Without header -> blocked.
    r0 = client.post(
        "/orders",
        json={
            "customer_name": "CSRF Buyer",
            "customer_email": email,
            "shipping_method": "personal_pickup",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert r0.status_code == 403, r0.text

    # With matching header -> allowed.
    r1 = client.post(
        "/orders",
        headers={"X-CSRF-Token": csrf_cookie},
        json={
            "customer_name": "CSRF Buyer",
            "customer_email": email,
            "shipping_method": "personal_pickup",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert r1.status_code == 201, r1.text

