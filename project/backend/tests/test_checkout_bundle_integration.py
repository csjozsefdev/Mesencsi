"""Integrációs tesztek: kombó kedvezmény + estimate + rendelés + Barion stub (SQLite teszt DB)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from database import SessionLocal
from db_models import AppUser, Product, ProductBundleDiscount, ShopOrder
from mesencsi import app
from password_utils import hash_password
from user_tokens import issue_user_access_token


def _auth_headers(user_id: int) -> dict[str, str]:
    return {"Authorization": "Bearer " + issue_user_access_token(user_id)}


def _checkout_order_body(customer_name: str, items: list[dict], **extra: object) -> dict:
    body: dict = {
        "customer_name": customer_name,
        "items": items,
        "shipping_method": "personal_pickup",
        "terms_accepted": True,
        "privacy_acknowledged": True,
        "company_website": "",
    }
    body.update(extra)
    return body


def _seed_verified_user_and_products() -> tuple[int, int, int]:
    """Vissza: user_id, product_a_id, product_b_id (árak 1000 és 2000 Ft)."""
    db = SessionLocal()
    try:
        u = AppUser(
            username="pytestbuyer",
            nickname=None,
            email="pytestbuyer@example.com",
            password_hash=hash_password("test-password-123"),
            phone=None,
            shipping_address=None,
            billing_address=None,
            short_bio=None,
            family_note=None,
            profile_image_url=None,
            is_active=True,
            is_banned=False,
            is_deleted=False,
            deleted_at=None,
            email_verified_at=datetime.now(UTC),
        )
        db.add(u)
        db.flush()
        pa = Product(name="Book A", price=1000, description="A")
        pb = Product(name="Book B", price=2000, description="B")
        db.add_all([pa, pb])
        db.commit()
        db.refresh(pa)
        db.refresh(pb)
        return u.id, pa.id, pb.id
    finally:
        db.close()


def _add_bundle_rule(name: str, product_ids: list[int], percent: int, *, active: bool = True) -> int:
    db = SessionLocal()
    try:
        prows = list(db.scalars(select(Product).where(Product.id.in_(product_ids))))
        rule = ProductBundleDiscount(
            name=name,
            description="test",
            percent_discount=percent,
            is_active=active,
            products=prows,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return int(rule.id)
    finally:
        db.close()

def _estimate(
    client: TestClient,
    user_id: int,
    items: list[dict],
    coupon: str | None = None,
    shipping_method: str = "personal_pickup",
) -> dict:
    body: dict = {"items": items, "shipping_method": shipping_method}
    if coupon:
        body["coupon_code"] = coupon
    r = client.post("/orders/estimate", json=body, headers=_auth_headers(user_id))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_estimate_single_line_no_combo_discount(client: TestClient) -> None:
    uid, pa, pb = _seed_verified_user_and_products()
    _add_bundle_rule("Pair", [pa, pb], 10)
    est = _estimate(client, uid, [{"product_id": pa, "quantity": 1}])
    assert est["grand_original"] == 1000
    assert est["grand_final"] == 1000
    assert est.get("bundle_rule_name") in (None, "")
    assert est.get("grand_discount", 0) == 0


def test_estimate_combo_applies_when_all_products_present(client: TestClient) -> None:
    uid, pa, pb = _seed_verified_user_and_products()
    _add_bundle_rule("Pair", [pa, pb], 10)
    est = _estimate(
        client,
        uid,
        [
            {"product_id": pa, "quantity": 1},
            {"product_id": pb, "quantity": 1},
        ],
    )
    assert est["grand_original"] == 3000
    assert est["bundle_rule_name"] == "Pair"
    assert est["bundle_percent"] == 10
    assert est["grand_discount"] == 300
    assert est["grand_final"] == 2700


def test_estimate_combo_not_applied_with_only_one_bundle_product(client: TestClient) -> None:
    uid, pa, pb = _seed_verified_user_and_products()
    _add_bundle_rule("Pair", [pa, pb], 10)
    est = _estimate(client, uid, [{"product_id": pa, "quantity": 3}])
    assert est["grand_original"] == 3000
    assert est["grand_final"] == 3000
    assert not est.get("bundle_rule_name")


def test_estimate_highest_percent_bundle_wins(client: TestClient) -> None:
    uid, pa, pb = _seed_verified_user_and_products()
    _add_bundle_rule("Low", [pa, pb], 10)
    _add_bundle_rule("High", [pa, pb], 25)
    est = _estimate(
        client,
        uid,
        [
            {"product_id": pa, "quantity": 1},
            {"product_id": pb, "quantity": 1},
        ],
    )
    assert est["bundle_percent"] == 25
    assert est["bundle_rule_name"] == "High"
    assert est["grand_discount"] == 750
    assert est["grand_final"] == 2250


def test_inactive_bundle_ignored_active_lower_percent_used(client: TestClient) -> None:
    uid, pa, pb = _seed_verified_user_and_products()
    _add_bundle_rule("InactiveBig", [pa, pb], 50, active=False)
    _add_bundle_rule("ActiveSmall", [pa, pb], 5)
    est = _estimate(
        client,
        uid,
        [
            {"product_id": pa, "quantity": 1},
            {"product_id": pb, "quantity": 1},
        ],
    )
    assert est["bundle_percent"] == 5
    assert est["bundle_rule_name"] == "ActiveSmall"
    assert est["grand_discount"] == 150


def test_order_and_barion_use_discounted_line_totals(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_SANDBOX", "true")
    uid, pa, pb = _seed_verified_user_and_products()
    _add_bundle_rule("Pair", [pa, pb], 10)
    est = _estimate(
        client,
        uid,
        [
            {"product_id": pa, "quantity": 1},
            {"product_id": pb, "quantity": 1},
        ],
    )
    assert est["grand_final"] == 2700

    r = client.post(
        "/orders",
        json=_checkout_order_body(
            "Teszt Vásárló",
            [
                {"product_id": pa, "quantity": 1},
                {"product_id": pb, "quantity": 1},
            ],
        ),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    rows = r.json()
    assert len(rows) == 2
    paid_sum = sum(int(x["total_price"]) for x in rows)
    assert paid_sum == 2700
    assert rows[0].get("bundle_rule_name") == "Pair" or rows[1].get("bundle_rule_name") == "Pair"

    ids = [int(x["id"]) for x in rows]
    br = client.post("/payments/barion/start", json={"order_ids": ids}, headers=_auth_headers(uid))
    assert br.status_code == 200, br.text
    assert br.json()["order_ids"] == ids

    db = SessionLocal()
    try:
        again = list(db.scalars(select(ShopOrder).where(ShopOrder.id.in_(ids))).all())
        assert sum(x.total_price for x in again) == 2700
    finally:
        db.close()


def test_production_barion_start_without_pos_key_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.delenv("BARION_POS_KEY", raising=False)
    uid, pa, pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body(
            "Prod Teszt",
            [{"product_id": pa, "quantity": 1}, {"product_id": pb, "quantity": 1}],
        ),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    ids = [int(x["id"]) for x in r.json()]
    br = client.post("/payments/barion/start", json={"order_ids": ids}, headers=_auth_headers(uid))
    assert br.status_code == 503
    assert "BARION_POS_KEY" in br.json().get("detail", "")


def test_production_barion_callback_forbidden_without_debug(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    r = client.post(
        "/payments/barion/callback",
        json={"payment_id": "preview-12345678", "status": "paid"},
    )
    assert r.status_code == 403


def test_production_barion_callback_allowed_with_internal_debug_header(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MESENCSI_INTERNAL_DEBUG_SECRET", "debug-token-ok-16b")
    uid, pa, pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Dbg Teszt", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    oid = int(r.json()[0]["id"])
    br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br.status_code == 200, br.text
    pid = br.json()["payment_id"]
    assert pid.startswith("preview-")

    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    r2 = client.post(
        "/payments/barion/callback",
        json={"payment_id": pid, "status": "paid"},
        headers={"X-Internal-Debug": "debug-token-ok-16b"},
    )
    assert r2.status_code == 204

    db = SessionLocal()
    try:
        row = db.get(ShopOrder, oid)
        assert row is not None
        assert row.payment_status == "paid"
    finally:
        db.close()
