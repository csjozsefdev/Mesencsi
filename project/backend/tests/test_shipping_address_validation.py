"""Shipping address validation — unit + order endpoint guards."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from shipping_address import (
    ShippingAddressValidationError,
    format_shipping_address_html,
    format_shipping_address_plain,
    sample_checkout_shipping_json,
    validate_address_parts,
    validate_checkout_shipping_address_parts,
    validate_hu_postal_code,
    zip_city_mismatch_warning,
)
from shipping_methods import GLS_HOME, PERSONAL_PICKUP
from tests.test_checkout_bundle_integration import (
    _auth_headers,
    _checkout_order_body,
    _seed_verified_user_and_products,
)


def test_hu_postal_code_exactly_four_digits() -> None:
    assert validate_hu_postal_code("1051") == "1051"
    with pytest.raises(ShippingAddressValidationError):
        validate_hu_postal_code("105")


def test_rejects_unsafe_markup() -> None:
    with pytest.raises(ShippingAddressValidationError):
        validate_address_parts(
            {
                "recipient_name": "<script>",
                "phone": "06301234567",
                "postal_code": "1051",
                "city": "Budapest",
                "street": "Teszt utca",
                "house_number": "1",
                "country": "Magyarország",
            }
        )


def test_zip_city_warning_budapest() -> None:
    assert zip_city_mismatch_warning("1051", "Debrecen") is not None
    assert zip_city_mismatch_warning("1051", "Budapest") is None


def test_format_html_escapes_markup() -> None:
    html_out = format_shipping_address_html("<script>alert(1)</script>")
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_checkout_address_uses_customer_name_when_recipient_empty() -> None:
    normalized = validate_checkout_shipping_address_parts(
        {
            "postal_code": "1051",
            "city": "Budapest",
            "street_line": "Teszt utca 12",
        },
        customer_name="Kovács Anna",
    )
    assert normalized["recipient_name"] == "Kovács Anna"
    assert normalized["phone"] is None
    assert normalized["street"] == "Teszt utca 12"
    assert normalized["country"] == "Magyarország"


def test_checkout_address_accepts_different_recipient() -> None:
    normalized = validate_checkout_shipping_address_parts(
        {
            "recipient_name": "Nagy Péter",
            "postal_code": "4024",
            "city": "Debrecen",
            "street_line": "Példa utca 3",
        },
        customer_name="Kovács Anna",
    )
    assert normalized["recipient_name"] == "Nagy Péter"


def test_checkout_address_requires_postal_city_street() -> None:
    with pytest.raises(ShippingAddressValidationError):
        validate_checkout_shipping_address_parts(
            {"city": "Budapest", "street_line": "Teszt utca 1"},
            customer_name="Teszt Elek",
        )
    with pytest.raises(ShippingAddressValidationError):
        validate_checkout_shipping_address_parts(
            {"postal_code": "1051", "street_line": "Teszt utca 1"},
            customer_name="Teszt Elek",
        )
    with pytest.raises(ShippingAddressValidationError):
        validate_checkout_shipping_address_parts(
            {"postal_code": "1051", "city": "Budapest"},
            customer_name="Teszt Elek",
        )


def test_format_plain_omits_phone_and_default_country() -> None:
    raw = sample_checkout_shipping_json(customer_name="Teszt Elek")
    text = format_shipping_address_plain(raw)
    assert "0630" not in text
    assert "Magyarország" not in text
    assert "Teszt Elek" in text
    assert "Teszt utca 12" in text


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_create_order_requires_shipping_method(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    bad = client.post(
        "/orders",
        json={
            "customer_name": "Teszt Vásárló",
            "items": [{"product_id": pa, "quantity": 1}],
            "company_website": "",
        },
        headers=_auth_headers(uid),
    )
    assert bad.status_code == 422

    ok = client.post(
        "/orders",
        json=_checkout_order_body(
            "Teszt Vásárló",
            [{"product_id": pa, "quantity": 1}],
            shipping_method=PERSONAL_PICKUP,
        ),
        headers=_auth_headers(uid),
    )
    assert ok.status_code == 201, ok.text


def test_gls_requires_valid_shipping_address(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    bad = client.post(
        "/orders",
        json=_checkout_order_body(
            "GLS Teszt",
            [{"product_id": pa, "quantity": 1}],
            shipping_method=GLS_HOME,
        ),
        headers=_auth_headers(uid),
    )
    assert bad.status_code == 422

    ok = client.post(
        "/orders",
        json=_checkout_order_body(
            "GLS Teszt",
            [{"product_id": pa, "quantity": 1}],
            shipping_method=GLS_HOME,
            shipping_address=sample_checkout_shipping_json(customer_name="Teszt Vásárló"),
        ),
        headers=_auth_headers(uid),
    )
    assert ok.status_code == 201, ok.text


def test_gls_order_without_recipient_uses_customer_name(client: TestClient) -> None:
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body(
            "GLS Same Recipient",
            [{"product_id": pa, "quantity": 1}],
            shipping_method=GLS_HOME,
            shipping_address=sample_checkout_shipping_json(customer_name="Teszt Vásárló"),
        ),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    import json

    meta = json.loads(r.json()[0]["shipping_address"])
    assert meta["recipient_name"] == "Teszt Vásárló"
