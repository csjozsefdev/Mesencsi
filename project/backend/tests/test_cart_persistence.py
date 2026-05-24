"""User cart survives PUT/GET across sessions (server-side)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import AppUser, Product
from mesencsi import app
from password_utils import hash_password
from user_tokens import issue_user_access_token


def _seed_user_and_product() -> tuple[int, int]:
    db = SessionLocal()
    try:
        u = AppUser(
            username="cartuser",
            email="cartuser@example.com",
            password_hash=hash_password("test-password-123"),
            is_active=True,
            is_banned=False,
            is_deleted=False,
            email_verified_at=datetime.now(UTC),
        )
        db.add(u)
        db.flush()
        p = Product(name="Cart Book", price=1500, description="d")
        db.add(p)
        db.commit()
        db.refresh(u)
        db.refresh(p)
        return int(u.id), int(p.id)
    finally:
        db.close()


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": "Bearer " + issue_user_access_token(user_id)}


def test_cart_put_get_and_clear() -> None:
    user_id, product_id = _seed_user_and_product()
    client = TestClient(app)
    headers = _auth(user_id)

    r0 = client.get("/cart", headers=headers)
    assert r0.status_code == 200
    assert r0.json() == []

    r1 = client.put(
        "/cart",
        headers=headers,
        json={"items": [{"product_id": product_id, "quantity": 2}]},
    )
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert len(body) == 1
    assert body[0]["product_id"] == product_id
    assert body[0]["quantity"] == 2
    assert body[0]["name"] == "Cart Book"

    r2 = client.get("/cart", headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["quantity"] == 2

    r3 = client.put("/cart", headers=headers, json={"items": []})
    assert r3.status_code == 200
    assert r3.json() == []
