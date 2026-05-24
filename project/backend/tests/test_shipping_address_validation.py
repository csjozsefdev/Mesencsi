"""Shipping address validation — unit + order endpoint guards."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from shipping_address import (
    ShippingAddressValidationError,
    format_shipping_address_html,
    sample_valid_shipping_json,
    validate_address_parts,
    validate_hu_postal_code,
    zip_city_mismatch_warning,
)
from tests.test_checkout_bundle_integration import _auth_headers, _seed_verified_user_and_products


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


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_create_order_requires_valid_shipping(client: TestClient) -> None:
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
        json={
            "customer_name": "Teszt Vásárló",
            "items": [{"product_id": pa, "quantity": 1}],
            "shipping_address": sample_valid_shipping_json(),
            "company_website": "",
        },
        headers=_auth_headers(uid),
    )
    assert ok.status_code == 201, ok.text
