"""Shipping methods: personal pickup + automatic GLS tiers; Foxpost blocked."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from payment_confirmation_email import _snapshot_from_orders
from shipping_address import sample_valid_shipping_json
from shipping_methods import (
    GLS_HOME,
    GLS_PRICE_LARGE,
    GLS_PRICE_MEDIUM,
    GLS_PRICE_SMALL,
    GLS_TIER_LARGE,
    GLS_TIER_MEDIUM,
    GLS_TIER_SMALL,
    PERSONAL_PICKUP,
    calculate_gls_shipping,
    count_shippable_item_quantity,
    public_shipping_method_options,
    recommend_gls_shipping,
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
def test_recommend_gls_shipping_tiers(qty, expected_price, expected_tier, expected_label) -> None:
    tier, price, label = recommend_gls_shipping(qty)
    assert tier == expected_tier
    assert price == expected_price
    assert label == expected_label
    assert calculate_gls_shipping(qty) == (tier, price, label)


def test_shop_config_lists_only_active_methods(client: TestClient) -> None:
    r = client.get("/shop/config")
    assert r.status_code == 200
    methods = r.json().get("shipping_methods") or []
    ids = {m["id"] for m in methods}
    assert ids == {PERSONAL_PICKUP, GLS_HOME}
    gls = next(m for m in methods if m["id"] == GLS_HOME)
    assert gls["price_huf"] is None
    assert gls["price_from_huf"] == GLS_PRICE_SMALL


def test_foxpost_rejected_on_order_create(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body(
            "Foxpost Teszt",
            [{"product_id": pa, "quantity": 1}],
            shipping_method="foxpost_locker",
            shipping_metadata={"provider": "foxpost", "locker_id": "FP123"},
        ),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 422


def test_personal_pickup_order_without_address(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body(
            "Átvétel Teszt",
            [{"product_id": pa, "quantity": 1}],
            shipping_method=PERSONAL_PICKUP,
        ),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    assert r.json()[0]["shipping_price"] == 0


@pytest.mark.parametrize(
    ("qty", "expected_price", "expected_tier", "expected_label"),
    [
        (1, GLS_PRICE_SMALL, GLS_TIER_SMALL, "Kis csomag"),
        (4, GLS_PRICE_MEDIUM, GLS_TIER_MEDIUM, "Közepes csomag"),
        (7, GLS_PRICE_LARGE, GLS_TIER_LARGE, "Nagy csomag"),
    ],
)
def test_gls_order_uses_auto_tier_from_quantity(
    client: TestClient,
    qty: int,
    expected_price: int,
    expected_tier: str,
    expected_label: str,
) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body(
            "GLS Teszt",
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
    assert meta.get("shippable_item_count") == qty


def test_gls_without_address_fails(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body(
            "GLS Hiány",
            [{"product_id": pa, "quantity": 1}],
            shipping_method=GLS_HOME,
        ),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 422


def test_gls_ignores_manipulated_server_metadata_fields(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body(
            "GLS Meta",
            [{"product_id": pa, "quantity": 4}],
            shipping_method=GLS_HOME,
            shipping_address=sample_valid_shipping_json(),
            shipping_metadata={
                "gls_package_tier": GLS_TIER_SMALL,
                "gls_price_huf": 100,
                "gls_package_label_hu": "Hamis csomag",
                "shippable_item_count": 1,
            },
        ),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    row = r.json()[0]
    assert row["shipping_price"] == GLS_PRICE_MEDIUM
    meta = row.get("shipping_metadata_json") or {}
    assert meta.get("gls_package_tier") == GLS_TIER_MEDIUM
    assert meta.get("gls_package_label_hu") == "Közepes csomag"
    assert meta.get("shippable_item_count") == 4


def test_estimate_auto_gls_tier(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    est = client.post(
        "/orders/estimate",
        json={"items": [{"product_id": pa, "quantity": 4}], "shipping_method": GLS_HOME},
        headers=_auth_headers(uid),
    )
    assert est.status_code == 200, est.text
    data = est.json()
    assert data["shipping_price"] == GLS_PRICE_MEDIUM
    assert data["shipping_package_label_hu"] == "Közepes csomag"


def test_barion_total_includes_gls_shipping(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body(
            "Barion Ship",
            [{"product_id": pa, "quantity": 1}],
            shipping_method=GLS_HOME,
            shipping_address=sample_valid_shipping_json(),
        ),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    oid = int(r.json()[0]["id"])

    from database import SessionLocal
    from shipping_methods import checkout_group_grand_total_huf

    db = SessionLocal()
    try:
        row = db.get(__import__("db_models").ShopOrder, oid)
        assert row is not None
        assert int(row.shipping_price) == GLS_PRICE_SMALL
        assert checkout_group_grand_total_huf([row]) == 1000 + GLS_PRICE_SMALL
    finally:
        db.close()

    br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br.status_code == 200, br.text


def test_payment_confirmation_snapshot_includes_gls_package() -> None:
    class _Row:
        id = 42
        checkout_group_id = "cg-ship"
        product_name = "Könyv"
        quantity = 4
        total_price = 4000
        shipping_method = GLS_HOME
        shipping_price = GLS_PRICE_MEDIUM
        shipping_metadata_json = {
            "gls_package_tier": GLS_TIER_MEDIUM,
            "gls_package_label_hu": "Közepes csomag",
            "shippable_item_count": 4,
        }
        customer_email = "buyer@example.com"
        customer_name = "Teszt"

    snap = _snapshot_from_orders("pay-1", [_Row()])
    assert snap is not None
    assert snap.shipping_price_huf == GLS_PRICE_MEDIUM
    assert snap.shipping_package_label_hu == "Közepes csomag"


def test_count_shippable_item_quantity_sums_quantities() -> None:
    class _Line:
        def __init__(self, quantity: int) -> None:
            self.quantity = quantity

    assert count_shippable_item_quantity([_Line(2), _Line(2)]) == 4


def test_public_options_never_include_foxpost() -> None:
    opts = public_shipping_method_options()
    ids = {str(o["id"]) for o in opts}
    assert "foxpost_locker" not in ids
