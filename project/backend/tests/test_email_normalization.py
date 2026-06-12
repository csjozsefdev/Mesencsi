"""Canonical shop email: lowercase storage and case-insensitive auth."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from database import SessionLocal
from db_models import AppUser
from mesencsi import app
from password_utils import hash_password
from user_password_reset import assign_reset_to_user, issue_reset_token
from user_tokens import issue_user_access_token


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_register_stores_lowercase_email(client: TestClient) -> None:
    email = "Mixed.Case.User@Example.COM"
    r = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "company_website": "",
        },
    )
    assert r.status_code == 201, r.text
    db = SessionLocal()
    try:
        row = db.scalar(select(AppUser).where(AppUser.email == email.lower()))
        assert row is not None
        assert row.email == "mixed.case.user@example.com"
    finally:
        db.close()


def test_duplicate_email_different_case_rejected(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "SecurePass123!", "company_website": ""},
    )
    r = client.post(
        "/auth/register",
        json={"email": "DUP@example.com", "password": "SecurePass123!", "company_website": ""},
    )
    assert r.status_code == 409


def test_mixed_case_login_works(client: TestClient) -> None:
    from tests.helpers import seed_verified_user

    password = "SecurePass123!"
    seed_verified_user(email="login.case@example.com", password=password, username="logincase")
    r = client.post("/auth/login", json={"email": "LOGIN.CASE@example.com", "password": password})
    assert r.status_code == 200, r.text


def test_password_reset_mixed_case_email(client: TestClient) -> None:
    from tests.helpers import seed_verified_user
    from user_password_reset import assign_reset_to_user, issue_reset_token

    uid = seed_verified_user(email="reset.case@example.com", password="old-password-12", username="resetcase")
    plain = issue_reset_token()
    with SessionLocal() as db:
        user = db.get(AppUser, uid)
        assert user is not None
        assign_reset_to_user(db, user, plain)
        db.commit()
    r = client.post(
        "/auth/reset-password",
        json={"token": plain, "password": "new-password-77", "password_confirm": "new-password-77"},
    )
    assert r.status_code == 200, r.text
    login = client.post(
        "/auth/login",
        json={"email": "RESET.CASE@example.com", "password": "new-password-77"},
    )
    assert login.status_code == 200, login.text
