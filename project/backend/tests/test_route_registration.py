"""Smoke tests: API/admin/media routes must register before frontend StaticFiles catch-all."""

from __future__ import annotations

from starlette.routing import Mount, Route

from mesencsi import app


def _mount_index(name: str) -> int:
    for i, route in enumerate(app.routes):
        if isinstance(route, Mount) and route.name == name:
            return i
    raise AssertionError(f"Mount {name!r} not found on app")


def _paths_before_mount(mount_name: str) -> list[str]:
    """Collect paths registered before the named static mount."""
    stop = _mount_index(mount_name)
    paths: list[str] = []

    for route in app.routes[:stop]:
        path_value = getattr(route, "path", None)
        if isinstance(path_value, str):
            paths.append(path_value)

        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            context = getattr(route, "include_context", None)
            prefix = getattr(context, "prefix", "") or ""

            for child in original_router.routes:
                child_path = getattr(child, "path", None)
                if isinstance(child_path, str):
                    paths.append(f"{prefix}{child_path}")

    return paths

def test_openapi_and_docs_available() -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200, openapi.text
        assert "openapi" in openapi.json()

        docs = client.get("/docs")
        assert docs.status_code == 200, docs.text


def test_media_mount_before_frontend_mount() -> None:
    media_i = _mount_index("media")
    frontend_i = _mount_index("frontend")
    assert media_i < frontend_i
    assert frontend_i == len(app.routes) - 1


def test_explicit_html_routes_before_static_mounts() -> None:
    paths = _paths_before_mount("media")
    assert "/admin/login" in paths
    assert "/admin" in paths
    assert "/" in paths


def test_router_prefixes_before_static_mounts() -> None:
    paths = _paths_before_mount("media")
    assert "/gallery" in paths
    assert "/health" in paths
    assert any(p.startswith("/payments/barion") for p in paths)


def test_live_routes_not_swallowed_by_static_files() -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200, health.text
        assert "status" in health.json()

        gallery = client.get("/gallery?page=1&page_size=1")
        assert gallery.status_code == 200, gallery.text
        assert gallery.headers.get("content-type", "").startswith("application/json")

        barion = client.get("/payments/barion/status")
        assert barion.status_code == 200, barion.text
        assert barion.headers.get("content-type", "").startswith("application/json")

        products = client.get("/products")
        assert products.status_code == 200, products.text
        assert isinstance(products.json(), list)


def test_admin_html_and_api_login_distinct() -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        login_page = client.get("/admin/login")
        assert login_page.status_code == 200, login_page.text
        assert "text/html" in login_page.headers.get("content-type", "")

        dashboard = client.get("/admin")
        assert dashboard.status_code == 200, dashboard.text
        assert "text/html" in dashboard.headers.get("content-type", "")

        # POST /admin/login is the API â€” must not 404 (static catch-all swallowing).
        api_login = client.post("/admin/login", json={})
        assert api_login.status_code != 404
        assert api_login.status_code in (422, 401)


def test_media_and_frontend_static_behavior() -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        missing_media = client.get("/media/uploads/no-such-file-xyz.png")
        assert missing_media.status_code == 404

        css = client.get("/style.css")
        assert css.status_code == 200, css.text
        assert "text/css" in css.headers.get("content-type", "")


def test_spa_shell_routes_and_unknown_path() -> None:
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        aszf = client.get("/aszf")
        assert aszf.status_code == 200, aszf.text
        assert "text/html" in aszf.headers.get("content-type", "")

        # No catch-all SPA shell: missing files 404; must not return storefront HTML.
        unknown = client.get("/no-such-storefront-route-xyz99")
        assert unknown.status_code == 404
        assert "text/html" not in unknown.headers.get("content-type", "")
