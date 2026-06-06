"""Authenticated password change — POST /auth/change-password."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import AppUser
from mesencsi import app
from password_utils import verify_password
from routers.user_auth import CHANGE_PASSWORD_SUCCESS_MSG, CHANGE_PASSWORD_WRONG_CURRENT_MSG
from tests.helpers import auth_headers, seed_verified_user


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_change_password_requires_auth(client: TestClient) -> None:
    r = client.post(
        "/auth/change-password",
        json={
            "current_password": "old-password-12",
            "password": "new-password-99",
            "password_confirm": "new-password-99",
        },
    )
    assert r.status_code == 401


def test_change_password_wrong_current(client: TestClient) -> None:
    uid = seed_verified_user(email="change-pw-bad@example.com", password="old-password-12")
    r = client.post(
        "/auth/change-password",
        headers=auth_headers(uid),
        json={
            "current_password": "wrong-current",
            "password": "new-password-99",
            "password_confirm": "new-password-99",
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == CHANGE_PASSWORD_WRONG_CURRENT_MSG


def test_change_password_success(client: TestClient) -> None:
    uid = seed_verified_user(email="change-pw-ok@example.com", password="old-password-12")
    r = client.post(
        "/auth/change-password",
        headers=auth_headers(uid),
        json={
            "current_password": "old-password-12",
            "password": "new-password-99",
            "password_confirm": "new-password-99",
        },
    )
    assert r.status_code == 200
    assert r.json()["message"] == CHANGE_PASSWORD_SUCCESS_MSG
    with SessionLocal() as db:
        user = db.get(AppUser, uid)
        assert user is not None
        assert verify_password("new-password-99", user.password_hash)
        assert user.password_reset_token_hash is None

    login_old = client.post(
        "/auth/login",
        json={"email": "change-pw-ok@example.com", "password": "old-password-12"},
    )
    assert login_old.status_code == 401
    login_new = client.post(
        "/auth/login",
        json={"email": "change-pw-ok@example.com", "password": "new-password-99"},
    )
    assert login_new.status_code == 200
