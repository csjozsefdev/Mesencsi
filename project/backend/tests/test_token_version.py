"""JWT token_version invalidation after password change and reset."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from tests.helpers import auth_headers, seed_verified_user
from user_password_reset import assign_reset_to_user, issue_reset_token
from user_tokens import issue_user_access_token
from database import SessionLocal
from db_models import AppUser


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_change_password_invalidates_old_token(client: TestClient) -> None:
    uid = seed_verified_user(email="tokver@example.com", password="old-password-12")
    old_headers = auth_headers(uid)
    old_token = old_headers["Authorization"].removeprefix("Bearer ").strip()
    r = client.post(
        "/auth/change-password",
        headers=old_headers,
        json={
            "current_password": "old-password-12",
            "password": "new-password-99",
            "password_confirm": "new-password-99",
        },
    )
    assert r.status_code == 200, r.text
    blocked = client.get("/orders", headers=old_headers)
    assert blocked.status_code == 401
    login = client.post(
        "/auth/login",
        json={"email": "tokver@example.com", "password": "new-password-99"},
    )
    assert login.status_code == 200, login.text
    new_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/orders", headers=new_headers).status_code == 200
    assert old_token  # referenced — old bearer must differ from new login token
    assert login.json()["access_token"] != old_token


def test_reset_password_invalidates_old_token(client: TestClient) -> None:
    uid = seed_verified_user(email="tokreset@example.com", password="old-password-12")
    old_token = issue_user_access_token(uid, token_version=0)
    plain = issue_reset_token()
    with SessionLocal() as db:
        user = db.get(AppUser, uid)
        assert user is not None
        assign_reset_to_user(db, user, plain)
        db.commit()
    r = client.post(
        "/auth/reset-password",
        json={"token": plain, "password": "new-password-88", "password_confirm": "new-password-88"},
    )
    assert r.status_code == 200, r.text
    assert (
        client.get("/orders", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    )
