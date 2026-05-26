"""Password reset flow — forgot/reset endpoints and token rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import AppUser
from mesencsi import app
from password_utils import verify_password
from routers.user_mvp import FORGOT_PASSWORD_GENERIC_MSG, RESET_PASSWORD_INVALID_MSG
from tests.helpers import seed_verified_user
from user_password_reset import RESET_TOKEN_TTL_MINUTES, assign_reset_to_user, issue_reset_token


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_forgot_password_unknown_email_generic_success(client: TestClient) -> None:
    with patch("routers.user_mvp.send_password_reset_email") as mock_send:
        r = client.post("/auth/forgot-password", json={"email": "unknown-reset@example.com"})
    assert r.status_code == 200
    assert r.json()["message"] == FORGOT_PASSWORD_GENERIC_MSG
    mock_send.assert_not_called()


def test_forgot_password_existing_user_sends_email(client: TestClient) -> None:
    uid = seed_verified_user(email="reset-user@example.com", password="old-password-12")
    captured: list[str] = []

    def _capture(to_email: str, token: str) -> bool:
        captured.append(token)
        return True

    with patch("routers.user_mvp.send_password_reset_email", side_effect=_capture):
        r = client.post("/auth/forgot-password", json={"email": "reset-user@example.com"})
    assert r.status_code == 200
    assert r.json()["message"] == FORGOT_PASSWORD_GENERIC_MSG
    assert len(captured) == 1
    with SessionLocal() as db:
        user = db.get(AppUser, uid)
        assert user is not None
        assert user.password_reset_token_hash is not None
        assert user.password_reset_sent_at is not None
        assert user.password_reset_used_at is None


def test_reset_password_valid_token_updates_hash(client: TestClient) -> None:
    uid = seed_verified_user(email="reset-ok@example.com", password="old-password-12")
    plain = issue_reset_token()
    with SessionLocal() as db:
        user = db.get(AppUser, uid)
        assert user is not None
        assign_reset_to_user(db, user, plain)
        db.commit()

    r = client.post(
        "/auth/reset-password",
        json={
            "token": plain,
            "password": "new-password-99",
            "password_confirm": "new-password-99",
        },
    )
    assert r.status_code == 200
    with SessionLocal() as db:
        user = db.get(AppUser, uid)
        assert user is not None
        assert verify_password("new-password-99", user.password_hash)
        assert user.password_reset_token_hash is None
        assert user.password_reset_used_at is not None

    login = client.post(
        "/auth/login",
        json={"email": "reset-ok@example.com", "password": "new-password-99"},
    )
    assert login.status_code == 200


def test_reset_password_invalid_token_fails(client: TestClient) -> None:
    r = client.post(
        "/auth/reset-password",
        json={
            "token": "not-a-valid-reset-token-value",
            "password": "new-password-99",
            "password_confirm": "new-password-99",
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == RESET_PASSWORD_INVALID_MSG


def test_reset_password_expired_token_fails(client: TestClient) -> None:
    uid = seed_verified_user(email="reset-exp@example.com", password="old-password-12")
    plain = issue_reset_token()
    with SessionLocal() as db:
        user = db.get(AppUser, uid)
        assert user is not None
        assign_reset_to_user(db, user, plain)
        user.password_reset_sent_at = datetime.now(UTC) - timedelta(minutes=RESET_TOKEN_TTL_MINUTES + 5)
        db.commit()

    r = client.post(
        "/auth/reset-password",
        json={
            "token": plain,
            "password": "new-password-99",
            "password_confirm": "new-password-99",
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == RESET_PASSWORD_INVALID_MSG


def test_reset_password_used_token_fails(client: TestClient) -> None:
    uid = seed_verified_user(email="reset-used@example.com", password="old-password-12")
    plain = issue_reset_token()
    with SessionLocal() as db:
        user = db.get(AppUser, uid)
        assert user is not None
        assign_reset_to_user(db, user, plain)
        db.commit()

    body = {
        "token": plain,
        "password": "new-password-99",
        "password_confirm": "new-password-99",
    }
    first = client.post("/auth/reset-password", json=body)
    assert first.status_code == 200
    second = client.post("/auth/reset-password", json=body)
    assert second.status_code == 400
    assert second.json()["detail"] == RESET_PASSWORD_INVALID_MSG
