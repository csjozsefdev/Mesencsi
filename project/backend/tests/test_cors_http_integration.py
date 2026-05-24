"""HTTP szintű CORS (dev alapértelmezés + preflight fejlécek). Production szabályok: test_cors_config + startup_config."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_cors_preflight_allows_dev_default_origin(client: TestClient) -> None:
    origin = "http://localhost:5173"
    r = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_get_includes_allow_origin_for_allowed(client: TestClient) -> None:
    origin = "http://127.0.0.1:5500"
    r = client.get("/health", headers={"Origin": origin})
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_disallowed_origin_not_reflected(client: TestClient) -> None:
    origin = "https://evil-unlisted.example.com"
    r = client.get("/health", headers={"Origin": origin})
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") != origin
