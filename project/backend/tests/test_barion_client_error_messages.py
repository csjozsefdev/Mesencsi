"""Barion gateway errors must not leak raw exception text to API clients."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from grafi_core.payments.barion_client import BarionApiHttpError
from routers.payments_barion import (
    _BARION_SHOP_DRAFT_CLIENT_MSG,
    _BARION_START_CLIENT_MSG,
    _BARION_STATE_CLIENT_MSG,
    _BARION_UNAVAILABLE_CLIENT_MSG,
)
from tests.test_checkout_bundle_integration import _auth_headers, _checkout_order_body, _seed_verified_user_and_products


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _barion_rest_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_POS_KEY", "test-pos-key-16chars")
    monkeypatch.setenv("BARION_PAYEE_EMAIL", "payee@example.com")


def test_get_payment_state_failure_returns_generic_detail(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _barion_rest_env(monkeypatch)
    uid, pa, _pb = _seed_verified_user_and_products()
    cr = client.post(
        "/orders",
        json=_checkout_order_body("Barion err", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert cr.status_code == 201, cr.text
    oid = cr.json()[0]["id"]

    with patch("routers.payments_barion.start_payment_request", return_value={"PaymentId": "pay-err-001"}):
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br.status_code == 200, br.text
    pid = br.json()["payment_id"]

    with patch("routers.payments_barion.get_payment_state", side_effect=RuntimeError("secret internal boom")):
        st = client.get(
            f"/payments/barion/payment/{pid}/state",
            headers=_auth_headers(uid),
        )
    assert st.status_code == 502, st.text
    assert st.json()["detail"] == _BARION_STATE_CLIENT_MSG
    assert "secret internal" not in st.text
    assert "RuntimeError" not in st.text


def test_start_payment_failure_returns_generic_detail(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _barion_rest_env(monkeypatch)
    uid, pa, _pb = _seed_verified_user_and_products()
    cr = client.post(
        "/orders",
        json=_checkout_order_body("Barion start err", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert cr.status_code == 201, cr.text
    oid = cr.json()[0]["id"]

    with patch(
        "routers.payments_barion.start_payment_request",
        side_effect=RuntimeError("upstream timeout xyzzy"),
    ):
        br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br.status_code == 502, br.text
    assert br.json()["detail"] == _BARION_START_CLIENT_MSG
    assert "xyzzy" not in br.text


def test_start_payment_shop_draft_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _barion_rest_env(monkeypatch)
    uid, pa, _pb = _seed_verified_user_and_products()
    cr = client.post(
        "/orders",
        json=_checkout_order_body("Barion draft", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert cr.status_code == 201, cr.text
    oid = cr.json()[0]["id"]
    draft_body = (
        '{"Errors":[{"Title":"Your shop is in draft state.",'
        '"ErrorCode":"ShopIsInDraftState"}]}'
    )
    with patch(
        "routers.payments_barion.start_payment_request",
        side_effect=BarionApiHttpError(401, draft_body, url="https://api.test.barion.com/v2/Payment/Start"),
    ):
        br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br.status_code == 503, br.text
    assert br.json()["detail"] == _BARION_SHOP_DRAFT_CLIENT_MSG
    assert "ShopIsInDraftState" not in br.text


def test_start_payment_config_error_returns_generic_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """ValueError from Barion config must not expose env var names to clients."""
    _barion_rest_env(monkeypatch)
    monkeypatch.delenv("BARION_PAYEE_EMAIL", raising=False)
    uid, pa, _pb = _seed_verified_user_and_products()
    cr = client.post(
        "/orders",
        json=_checkout_order_body("Barion cfg", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert cr.status_code == 201, cr.text
    oid = cr.json()[0]["id"]
    br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br.status_code in (502, 503), br.text
    if br.status_code == 503:
        assert br.json()["detail"] == _BARION_UNAVAILABLE_CLIENT_MSG
        assert "BARION_PAYEE_EMAIL" not in br.text
