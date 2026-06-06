"""Admin cookie auth + CSRF: unsafe actions require X-CSRF-Token."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from auth import create_admin_token
from database import SessionLocal
from db_models import AppUser
from mesencsi import app
from password_utils import hash_password


def _seed_user() -> int:
    db = SessionLocal()
    try:
        u = AppUser(
            username="csrfdeluser",
            email="csrfdeluser@example.com",
            password_hash=hash_password("test-password-123"),
            is_active=True,
            is_banned=False,
            is_deleted=False,
            email_verified_at=datetime.now(UTC),
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return int(u.id)
    finally:
        db.close()


def test_admin_delete_user_requires_csrf_cookie_and_header() -> None:
    user_id = _seed_user()
    client = TestClient(app)

    # Cookie-based admin auth
    admin_token = create_admin_token(username="pytest-admin", role="owner")
    client.cookies.set("mesencsi_admin_token", admin_token, path="/")

    # Missing CSRF -> blocked
    r0 = client.delete(f"/admin/users/{user_id}")
    assert r0.status_code == 403, r0.text

    # With CSRF cookie + matching header -> allowed
    client.cookies.set("mesencsi_csrf", "csrf-test-token-1", path="/")
    r1 = client.delete(f"/admin/users/{user_id}", headers={"X-CSRF-Token": "csrf-test-token-1"})
    assert r1.status_code == 204, r1.text

