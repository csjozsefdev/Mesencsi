"""Integration tests for the grafi_core demo backend."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from demo_backend.incidents import demo_incidents_snapshot
from grafi_core.security.csrf import CSRF_HEADER
from grafi_core.security.headers import SECURITY_HEADER_VALUES


def test_health_live(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["app"] == "grafi_demo"
    assert body["production"] is False


def test_security_headers_on_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    for name, value in SECURITY_HEADER_VALUES.items():
        assert r.headers.get(name) == value, name


def test_request_id_header(client: TestClient) -> None:
    r = client.get("/health", headers={"X-Request-ID": "demo-req-123"})
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID") == "demo-req-123"


def test_jwt_smoke_roundtrip(client: TestClient) -> None:
    r = client.get("/auth/jwt-smoke")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["issued_for"] == 42
    assert body["parsed_user_id"] == 42
    assert body["token_prefix"]


def test_smoke_login_and_me(client: TestClient) -> None:
    login = client.post("/auth/smoke-login", json={"user_id": 7})
    assert login.status_code == 200, login.text
    assert login.json()["user_id"] == 7
    assert client.cookies.get("demo_user_token")
    assert client.cookies.get("demo_csrf")

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["user_id"] == 7


def test_csrf_endpoint_sets_cookie(client: TestClient) -> None:
    r = client.get("/auth/csrf")
    assert r.status_code == 200
    assert r.json().get("csrf_token")
    assert client.cookies.get("demo_csrf")


def test_csrf_blocks_unsafe_cookie_auth_without_header(client: TestClient) -> None:
    client.post("/auth/smoke-login", json={"user_id": 1})
    r = client.post("/auth/smoke-action", json={})
    assert r.status_code == 403, r.text


def test_csrf_allows_unsafe_with_matching_header(client: TestClient) -> None:
    client.post("/auth/smoke-login", json={"user_id": 1})
    csrf = client.cookies.get("demo_csrf")
    assert csrf
    r = client.post(
        "/auth/smoke-action",
        json={},
        headers={CSRF_HEADER: csrf},
    )
    assert r.status_code == 200, r.text
    assert r.json()["user_id"] == 1


def test_incident_persist_on_unhandled_error(client: TestClient) -> None:
    r = client.get("/health/raise-test")
    assert r.status_code == 500, r.text
    assert r.headers.get("X-Request-ID")
    incidents = demo_incidents_snapshot()
    assert len(incidents) == 1
    assert incidents[0]["error_type"] == "RuntimeError"
    assert incidents[0]["path"] == "/health/raise-test"


def test_raise_test_hidden_outside_pytest(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    r = client.get("/health/raise-test")
    assert r.status_code == 404


_MESENCSI_MARKERS = (
    "mesencsi",
    "db_models",
    "mesencsi_settings",
    "adapters.login_throttle",
    "adapters.user_auth",
    "adapters.incidents",
)


def test_demo_backend_has_no_mesencsi_imports() -> None:
    demo_root = Path(__file__).resolve().parent.parent
    offenders: list[str] = []
    for path in demo_root.rglob("*.py"):
        if path.parts[-2:] == ("tests", path.name):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    if any(marker in mod for marker in _MESENCSI_MARKERS):
                        offenders.append(f"{path.name}: import {mod}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                if any(marker in mod for marker in _MESENCSI_MARKERS):
                    offenders.append(f"{path.name}: from {mod}")
    assert not offenders, "Mesencsi imports found:\n" + "\n".join(offenders)
