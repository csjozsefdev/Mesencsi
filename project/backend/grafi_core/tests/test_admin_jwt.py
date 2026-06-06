from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from grafi_core.auth.admin_jwt import issue_admin_access_token, parse_admin_access_token
from grafi_core.auth.user_jwt import issue_user_access_token
from grafi_core.settings.jwt_settings import AdminJwtSettings


def test_admin_jwt_roundtrip_owner() -> None:
    token = issue_admin_access_token(username="owner", role="owner")
    username, role = parse_admin_access_token(token)
    assert username == "owner"
    assert role == "owner"


def test_admin_jwt_roundtrip_maintenance() -> None:
    token = issue_admin_access_token(username="maint", role="maintenance")
    username, role = parse_admin_access_token(token)
    assert username == "maint"
    assert role == "maintenance"


def test_admin_jwt_expired_rejected() -> None:
    secret = "grafi-test-admin-jwt-secret-not-for-production"
    past = datetime.now(UTC) - timedelta(hours=2)
    token = jwt.encode(
        {
            "sub": "owner",
            "role": "owner",
            "typ": "admin",
            "iat": int(past.timestamp()),
            "exp": int((past + timedelta(minutes=5)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        parse_admin_access_token(token)
    assert exc.value.status_code == 401


def test_shop_token_rejected_by_admin_parser() -> None:
    shop_token = issue_user_access_token(99)
    with pytest.raises(HTTPException) as exc:
        parse_admin_access_token(shop_token)
    assert exc.value.status_code == 401


def test_admin_jwt_invalid_role_rejected() -> None:
    secret = "grafi-test-admin-jwt-secret-not-for-production"
    token = jwt.encode(
        {
            "sub": "owner",
            "role": "superadmin",
            "typ": "admin",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        parse_admin_access_token(token, jwt_settings=AdminJwtSettings())
    assert exc.value.status_code == 401
