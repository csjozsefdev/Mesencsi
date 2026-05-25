"""HTTP security headers on API, HTML, errors, and redirects."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from security_headers import SECURITY_HEADER_VALUES


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _assert_security_headers(response) -> None:
    for name, value in SECURITY_HEADER_VALUES.items():
        assert response.headers.get(name) == value, f"missing or wrong {name}"


def test_security_headers_on_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200, r.text
    _assert_security_headers(r)


def test_security_headers_on_storefront_html(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200, r.text
    assert "text/html" in (r.headers.get("content-type") or "")
    _assert_security_headers(r)


def test_security_headers_on_not_found(client: TestClient) -> None:
    r = client.get("/__mesencsi_security_headers_missing_route__")
    assert r.status_code == 404, r.text
    _assert_security_headers(r)


def test_security_headers_on_redirect(client: TestClient) -> None:
    """Barion return and other redirects still get headers; Location is unchanged."""
    r = client.get("/payments/barion/return", follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    assert r.headers.get("location")
    _assert_security_headers(r)
