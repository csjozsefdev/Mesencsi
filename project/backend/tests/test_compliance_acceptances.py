from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from database import SessionLocal
from db_models import AppUser, ShopOrder
from mesencsi import app
from policy_versions import PRIVACY_POLICY_VERSION, TERMS_VERSION
from tests.test_checkout_bundle_integration import (
    _auth_headers,
    _checkout_order_body,
    _seed_verified_user_and_products,
)


def _registration_body(**overrides: object) -> dict:
    body = {
        "email": "compliance-register@example.com",
        "password": "Test1234!",
        "password_confirm": "Test1234!",
        "terms_accepted": True,
        "privacy_acknowledged": True,
    }
    body.update(overrides)
    return body


def test_registration_rejects_missing_or_false_acceptances() -> None:
    with TestClient(app) as client:
        assert client.post("/auth/register", json=_registration_body(terms_accepted=False)).status_code == 422
        assert client.post("/auth/register", json=_registration_body(privacy_acknowledged=False)).status_code == 422
        missing = _registration_body()
        missing.pop("terms_accepted")
        assert client.post("/auth/register", json=missing).status_code == 422


def test_registration_persists_server_policy_versions() -> None:
    with TestClient(app) as client:
        with patch("routers.user_auth.send_email_verification", return_value=True):
            response = client.post("/auth/register", json=_registration_body())
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(AppUser.email == "compliance-register@example.com"))
        assert user is not None
        assert user.terms_accepted_at is not None
        assert user.terms_version == TERMS_VERSION
        assert user.privacy_acknowledged_at is not None
        assert user.privacy_version == PRIVACY_POLICY_VERSION


def test_checkout_rejects_missing_or_false_acceptances() -> None:
    uid, product_id, _ = _seed_verified_user_and_products()
    with TestClient(app) as client:
        body = _checkout_order_body("Buyer", [{"product_id": product_id, "quantity": 1}])
        body["terms_accepted"] = False
        assert client.post("/orders", json=body, headers=_auth_headers(uid)).status_code == 422

        body = _checkout_order_body("Buyer", [{"product_id": product_id, "quantity": 1}])
        body.pop("privacy_acknowledged")
        assert client.post("/orders", json=body, headers=_auth_headers(uid)).status_code == 422


def test_checkout_persists_server_policy_versions() -> None:
    uid, product_id, _ = _seed_verified_user_and_products()
    with TestClient(app) as client:
        response = client.post(
            "/orders",
            json=_checkout_order_body("Buyer", [{"product_id": product_id, "quantity": 1}]),
            headers=_auth_headers(uid),
        )
    assert response.status_code == 201, response.text
    order_id = int(response.json()[0]["id"])
    with SessionLocal() as db:
        row = db.get(ShopOrder, order_id)
        assert row is not None
        assert row.terms_accepted_at is not None
        assert row.terms_version == TERMS_VERSION
        assert row.privacy_acknowledged_at is not None
        assert row.privacy_version == PRIVACY_POLICY_VERSION


def test_all_legal_routes_serve_storefront_shell() -> None:
    with TestClient(app) as client:
        for route in (
            "/aszf",
            "/adatkezeles",
            "/impresszum",
            "/elallas",
            "/szallitas",
            "/fizetes",
            "/panaszkezeles",
            "/sutik",
        ):
            response = client.get(route)
            assert response.status_code == 200, route
            assert "text/html" in response.headers.get("content-type", "")
