"""Public shop config endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_shop_config_default(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHOP_PRODUCTS_COMING_SOON", raising=False)
    r = client.get("/shop/config")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["products_coming_soon"] is False
    assert data.get("products_coming_soon_message") in (None, "")


def test_shop_config_coming_soon(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOP_PRODUCTS_COMING_SOON", "true")
    monkeypatch.setenv(
        "SHOP_PRODUCTS_COMING_SOON_MESSAGE",
        "Teszt üzenet — hamarosan.",
    )
    r = client.get("/shop/config")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["products_coming_soon"] is True
    assert data["products_coming_soon_message"] == "Teszt üzenet — hamarosan."
