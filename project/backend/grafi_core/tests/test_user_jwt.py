from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from grafi_core.auth.user_jwt import issue_user_access_token, parse_user_access_token
from grafi_core.settings.jwt_settings import ShopJwtSettings


def test_user_jwt_roundtrip() -> None:
    token = issue_user_access_token(42)
    assert parse_user_access_token(token) == (42, 0)


def test_user_jwt_wrong_typ_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "grafi-test-user-jwt-secret-not-for-production"
    token = jwt.encode(
        {"sub": "42", "typ": "admin", "iat": int(datetime.now(UTC).timestamp()), "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp())},
        secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        parse_user_access_token(token)
    assert exc.value.status_code == 401


def test_user_jwt_expired_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "grafi-test-user-jwt-secret-not-for-production"
    past = datetime.now(UTC) - timedelta(hours=2)
    token = jwt.encode(
        {
            "sub": "42",
            "typ": "user",
            "iat": int(past.timestamp()),
            "exp": int((past + timedelta(minutes=5)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        parse_user_access_token(token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


def test_user_jwt_malformed_sub_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "grafi-test-user-jwt-secret-not-for-production"
    token = jwt.encode(
        {
            "sub": "not-an-int",
            "typ": "user",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        parse_user_access_token(token)
    assert exc.value.status_code == 401


def test_user_jwt_missing_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("USER_JWT_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc:
        issue_user_access_token(1)
    assert exc.value.status_code == 500


def test_user_jwt_custom_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUSTOM_USER_JWT_SECRET", "custom-secret-key-for-tests-only-xx")
    settings = ShopJwtSettings(secret_env_key="CUSTOM_USER_JWT_SECRET")
    token = issue_user_access_token(7, jwt_settings=settings)
    assert parse_user_access_token(token, jwt_settings=settings) == (7, 0)
