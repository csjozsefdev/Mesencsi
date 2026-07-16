"""GLS package tier: automatic from cart quantity; server validates price."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from shipping_address import sample_valid_shipping_json
from shipping_methods import (
    GLS_HOME,
    GLS_PRICE_LARGE,
    GLS_PRICE_MEDIUM,
    GLS_PRICE_SMALL,
    GLS_TIER_LARGE,
    GLS_TIER_MEDIUM,
    GLS_TIER_SMALL,
)
from tests.test_checkout_bundle_integration import (
    _auth_headers,
    _checkout_order_body,
    _seed_verified_user_and_products,
)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize(
    ("qty", "expected_price", "expected_tier", "expected_label"),
    [
        (1, GLS_PRICE_SMALL, GLS_TIER_SMALL, "Kis csomag"),
        (3, GLS_PRICE_SMALL, GLS_TIER_SMALL, "Kis csomag"),
        (4, GLS_PRICE_MEDIUM, GLS_TIER_MEDIUM, "Közepes csomag"),
        (6, GLS_PRICE_MEDIUM, GLS_TIER_MEDIUM, "Közepes csomag"),
        (7, GLS_PRICE_LARGE, GLS_TIER_LARGE, "Nagy csomag"),
    ],
)
def test_gls_estimate_auto_tier_from_quantity(
    client: TestClient,
    qty: int,
    expected_price: int,
    expected_tier: str,
    expected_label: str,
) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    est = client.post(
        "/orders/estimate",
        json={"items": [{"product_id": pa, "quantity": qty}], "shipping_method": GLS_HOME},
        headers=_auth_headers(uid),
    )
    assert est.status_code == 200, est.text
    data = est.json()
    assert data["shipping_price"] == expected_price
    assert data["shipping_package_label_hu"] == expected_label
    assert data["shippable_item_count"] == qty

    r = client.post(
        "/orders",
        json=_checkout_order_body(
            f"GLS auto {qty}",
            [{"product_id": pa, "quantity": qty}],
            shipping_method=GLS_HOME,
            shipping_address=sample_valid_shipping_json(),
        ),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    row = r.json()[0]
    assert row["shipping_price"] == expected_price
    meta = row.get("shipping_metadata_json") or {}
    assert meta.get("gls_package_tier") == expected_tier
    assert meta.get("gls_package_label_hu") == expected_label


def test_gls_ignores_client_tier_manipulation(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    est = client.post(
        "/orders/estimate",
        json={
            "items": [{"product_id": pa, "quantity": 1}],
            "shipping_method": GLS_HOME,
            "shipping_metadata": {"gls_package_tier": GLS_TIER_LARGE},
        },
        headers=_auth_headers(uid),
    )
    assert est.status_code == 200, est.text
    assert est.json()["shipping_price"] == GLS_PRICE_SMALL

    r = client.post(
        "/orders",
        json=_checkout_order_body(
            "GLS ignore client tier",
            [{"product_id": pa, "quantity": 1}],
            shipping_method=GLS_HOME,
            shipping_address=sample_valid_shipping_json(),
            shipping_metadata={"gls_package_tier": GLS_TIER_LARGE},
        ),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    row = r.json()[0]
    assert row["shipping_price"] == GLS_PRICE_SMALL
    meta = row.get("shipping_metadata_json") or {}
    assert meta.get("gls_package_tier") == GLS_TIER_SMALL


def test_shop_config_exposes_gls_package_options(client: TestClient) -> None:
    r = client.get("/shop/config")
    assert r.status_code == 200
    opts = r.json().get("gls_package_options") or []
    assert len(opts) == 3
    ids = {o["id"] for o in opts}
    assert ids == {GLS_TIER_SMALL, GLS_TIER_MEDIUM, GLS_TIER_LARGE}
