"""OpenAPI schema endpoints: available in dev/test, disabled in production."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import mesencsi
from openapi_docs import fastapi_openapi_kwargs


def test_openapi_docs_available_in_dev_mode() -> None:
    """Default test app import: MESENCSI_PRODUCTION unset — schema UI is reachable."""
    assert fastapi_openapi_kwargs() == {}
    assert mesencsi.app.openapi_url == "/openapi.json"
    assert mesencsi.app.docs_url == "/docs"
    assert mesencsi.app.redoc_url == "/redoc"
    with TestClient(mesencsi.app) as client:
        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200, openapi.text
        assert "openapi" in openapi.json()

        docs = client.get("/docs")
        assert docs.status_code == 200, docs.text

        redoc = client.get("/redoc")
        assert redoc.status_code == 200, redoc.text


def test_openapi_kwargs_disable_routes_in_production_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same kwargs passed to FastAPI() in mesencsi when MESENCSI_PRODUCTION is set at process start."""
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    assert fastapi_openapi_kwargs() == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
    prod_app = FastAPI(**fastapi_openapi_kwargs())
    assert prod_app.openapi_url is None
    assert prod_app.docs_url is None
    assert prod_app.redoc_url is None
    with TestClient(prod_app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_openapi_docs_unavailable_in_production_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production flag → no registered schema routes (404), matching mesencsi app creation."""
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    kwargs = fastapi_openapi_kwargs(production=True)
    prod_app = FastAPI(**kwargs)
    with TestClient(prod_app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404


def test_openapi_json_unavailable_in_production_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    prod_app = FastAPI(**fastapi_openapi_kwargs(production=True))
    with TestClient(prod_app) as client:
        assert client.get("/openapi.json").status_code == 404
