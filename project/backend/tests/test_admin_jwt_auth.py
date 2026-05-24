"""Admin JWT: aláírás, lejárat, role elkülönítés, shop token elutasítás."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from admin_tokens import ADMIN_JWT_ALG, parse_admin_access_token
from auth import create_admin_token
from mesencsi import app
from tests.test_checkout_bundle_integration import _seed_verified_user_and_products
from user_tokens import issue_user_access_token


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_admin_jwt_roundtrip_owner() -> None:
    tok = create_admin_token(username="owner", role="owner")
    assert tok.count(".") == 2
    u, r = parse_admin_access_token(tok)
    assert u == "owner" and r == "owner"


def test_invalid_admin_token_rejected(client: TestClient) -> None:
    r = client.get(
        "/admin/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert r.status_code == 401


def test_expired_admin_token_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "pytest-admin-jwt-secret-not-for-production-xx"
    past = datetime.now(UTC) - timedelta(hours=1)
    tok = jwt.encode(
        {
            "sub": "owner",
            "role": "owner",
            "typ": "admin",
            "iat": int(past.timestamp()),
            "exp": int((past + timedelta(minutes=5)).timestamp()),
        },
        secret,
        algorithm=ADMIN_JWT_ALG,
    )
    r = client.get("/admin/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401
    assert "lejárt" in r.json().get("detail", "").lower()


def test_legacy_pipe_admin_token_rejected(client: TestClient) -> None:
    r = client.get("/admin/me", headers={"Authorization": "Bearer owner|owner"})
    assert r.status_code == 401


def test_owner_token_accesses_admin_me(client: TestClient) -> None:
    tok = create_admin_token(username="owner", role="owner")
    r = client.get("/admin/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["role"] == "owner"


def test_maintenance_token_lists_orders(client: TestClient) -> None:
    tok = create_admin_token(username="maint", role="maintenance")
    r = client.get("/admin/orders", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200


def test_maintenance_cannot_create_product_owner_only(client: TestClient) -> None:
    tok = create_admin_token(username="maint", role="maintenance")
    r = client.post(
        "/admin/products",
        json={"name": "X", "price": 100, "description": "d"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 403


def test_shop_user_token_rejected_on_admin_route(client: TestClient) -> None:
    uid, _pa, _pb = _seed_verified_user_and_products()
    shop_tok = issue_user_access_token(uid)
    r = client.get("/admin/me", headers={"Authorization": f"Bearer {shop_tok}"})
    assert r.status_code == 401
