"""Registration email verification + resend (cookie auth + CSRF)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from database import SessionLocal
from db_models import AppUser
from email_errors import EmailSendError
from mesencsi import app
from tests.helpers import seed_unverified_user, seed_verified_user
from user_email_verify import assign_verification_to_user, issue_verification_token
from user_password_reset import issue_reset_token


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_register_saves_verification_token_when_email_not_sent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("MESENCSI_PRODUCTION", "false")
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.brevo.com")
    email = "reg-verify-flow@example.com"
    with patch("routers.user_auth.send_email_verification", return_value=False):
        r = client.post(
            "/auth/register",
            json={"email": email, "password": "Test1234!", "password_confirm": "Test1234!", "terms_accepted": True, "privacy_acknowledged": True},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("verification_email_sent") is False
    assert "LOCAL DEV AUTH EMAIL" in (body.get("message") or "")
    assert "SMTP beállításait" not in (body.get("message") or "")
    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(AppUser.email == email))
        assert user is not None
        assert user.email_verification_token
        assert user.email_verified_at is None


def test_verify_email_valid_token_marks_verified(client: TestClient) -> None:
    uid = seed_unverified_user(email="verify-ok@example.com", username="verifyok")
    plain = issue_verification_token()
    with SessionLocal() as db:
        user = db.get(AppUser, uid)
        assert user is not None
        assign_verification_to_user(db, user, plain)
        db.commit()

    r = client.get(f"/auth/verify-email?token={plain}")
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    with SessionLocal() as db:
        user = db.get(AppUser, uid)
        assert user is not None
        assert user.email_verified_at is not None
        assert user.email_verification_token is None


def test_verify_email_invalid_token_fails(client: TestClient) -> None:
    r = client.get("/auth/verify-email?token=not-a-valid-verification-token")
    assert r.status_code == 400
    assert "lejárt" in r.json().get("detail", "").lower() or "érvénytelen" in r.json().get("detail", "").lower()


def test_resend_verification_dev_logged_returns_200(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("MESENCSI_PRODUCTION", raising=False)
    email = "resend-dev@example.com"
    password = "Test1234!"
    seed_unverified_user(email=email, password=password, username="resenddev")

    lr = client.post("/auth/login", json={"email": email, "password": password})
    assert lr.status_code == 200, lr.text
    csrf = client.cookies.get("mesencsi_csrf")
    assert csrf

    with patch("routers.user_auth.send_email_verification", return_value=False):
        r = client.post(
            "/auth/resend-verification",
            headers={"X-CSRF-Token": csrf},
            json={},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert body.get("verification_email_sent") is False
    assert body.get("message")


def test_resend_verification_requires_csrf_when_cookie_auth(client: TestClient) -> None:
    email = "resend-csrf@example.com"
    password = "Test1234!"
    seed_unverified_user(email=email, password=password, username="resendcsrf")

    lr = client.post("/auth/login", json={"email": email, "password": password})
    assert lr.status_code == 200, lr.text

    with patch("routers.user_auth.send_email_verification", return_value=True):
        r = client.post("/auth/resend-verification", json={})
    assert r.status_code == 403, r.text


def test_forgot_password_exempt_from_csrf(client: TestClient) -> None:
    with patch("routers.user_auth.send_password_reset_email", return_value=False):
        r = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200


def test_register_local_smtp_failure_returns_201_not_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "false")
    monkeypatch.delenv("RENDER", raising=False)
    email = "reg-smtp-fail-local@example.com"
    caplog.set_level("WARNING")
    with patch("email_outbound.send_plain_email", side_effect=EmailSendError("SMTP delivery failed")):
        r = client.post(
            "/auth/register",
            json={"email": email, "password": "Test1234!", "password_confirm": "Test1234!", "terms_accepted": True, "privacy_acknowledged": True},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("verification_email_sent") is False
    assert "LOCAL DEV AUTH EMAIL" in caplog.text


def test_register_production_smtp_failure_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    email = "reg-smtp-fail-prod@example.com"
    with patch(
        "routers.user_auth.send_email_verification",
        side_effect=EmailSendError("SMTP delivery failed"),
    ):
        r = client.post(
            "/auth/register",
            json={"email": email, "password": "Test1234!", "password_confirm": "Test1234!", "terms_accepted": True, "privacy_acknowledged": True},
        )
    assert r.status_code == 503, r.text
    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(AppUser.email == email))
        assert user is not None


def test_forgot_password_local_logs_reset_link(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "false")
    email = "forgot-local@example.com"
    seed_verified_user(email=email, password="OldPass123!", username="forgotlocal")
    caplog.set_level("WARNING")
    with patch("email_outbound.send_plain_email", side_effect=EmailSendError("SMTP delivery failed")):
        r = client.post("/auth/forgot-password", json={"email": email})
    assert r.status_code == 200, r.text
    assert "LOCAL DEV AUTH EMAIL" in caplog.text
    assert "reset-password.html?token=" in caplog.text


def test_reset_password_link_works_after_forgot(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "false")
    email = "reset-flow@example.com"
    seed_verified_user(email=email, password="OldPass123!", username="resetflow")
    plain = issue_reset_token()
    with SessionLocal() as db:
        from user_password_reset import assign_reset_to_user

        user = db.scalar(select(AppUser).where(AppUser.email == email))
        assert user is not None
        assign_reset_to_user(db, user, plain)
        db.commit()

    r = client.post(
        "/auth/reset-password",
        json={
            "token": plain,
            "password": "NewPass999!",
            "password_confirm": "NewPass999!",
        },
    )
    assert r.status_code == 200, r.text

    login_old = client.post("/auth/login", json={"email": email, "password": "OldPass123!"})
    assert login_old.status_code == 401

    login_new = client.post("/auth/login", json={"email": email, "password": "NewPass999!"})
    assert login_new.status_code == 200, login_new.text


def test_verified_user_can_login_after_verify(client: TestClient) -> None:
    email = "login-after-verify@example.com"
    password = "Test1234!"
    uid = seed_unverified_user(email=email, password=password, username="loginafterv")
    plain = issue_verification_token()
    with SessionLocal() as db:
        user = db.get(AppUser, uid)
        assert user is not None
        assign_verification_to_user(db, user, plain)
        db.commit()

    vr = client.get(f"/auth/verify-email?token={plain}")
    assert vr.status_code == 200

    lr = client.post("/auth/login", json={"email": email, "password": password})
    assert lr.status_code == 200, lr.text
    assert client.cookies.get("mesencsi_user_token")

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json().get("email_verified_at")
