"""HTTP integráció: login throttle (sikertelen próbák → zárolás, sikeres login törli)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import AppUser, LoginThrottle
from login_throttle import MAX_FAILS
from mesencsi import app
from password_utils import hash_password
from tests.helpers import seed_verified_user


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _login_body(email: str, password: str) -> dict[str, str]:
    return {"email": email, "password": password}


def test_failed_logins_trigger_throttle_then_success_clears(client: TestClient) -> None:
    email = "throttle-user@example.com"
    good_password = "correct-password-123"
    seed_verified_user(email=email, password=good_password, username="throttleuser")

    wrong = _login_body(email, "wrong-password")
    for _ in range(MAX_FAILS):
        r = client.post("/auth/login", json=wrong)
        assert r.status_code == 401, r.text

    locked = client.post("/auth/login", json=wrong)
    assert locked.status_code == 429, locked.text
    assert "várj" in locked.json().get("detail", "").lower() or "belépési" in locked.json().get("detail", "").lower()

    # Sikeres login törli a throttle sort (zárolás előtti userrel)
    email2 = "throttle-clear@example.com"
    seed_verified_user(email=email2, password=good_password, username="throttleclear")
    client.post("/auth/login", json=_login_body(email2, "wrong"))
    ok = client.post("/auth/login", json=_login_body(email2, good_password))
    assert ok.status_code == 200, ok.text

    db = SessionLocal()
    try:
        row = db.get(LoginThrottle, email2.strip().lower())
        assert row is None
    finally:
        db.close()


def test_successful_login_after_few_failures_not_locked(client: TestClient) -> None:
    email = "throttle-partial@example.com"
    password = "good-password-99"
    seed_verified_user(email=email, password=password, username="throttlepartial")

    for _ in range(MAX_FAILS - 1):
        assert client.post("/auth/login", json=_login_body(email, "bad")).status_code == 401

    ok = client.post("/auth/login", json=_login_body(email, password))
    assert ok.status_code == 200, ok.text
    assert ok.json().get("access_token")
