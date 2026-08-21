"""Barion Base Pixel injection on public storefront HTML."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from barion_pixel import barion_pixel_markup, inject_barion_pixel


@pytest.fixture
def pixel_id(monkeypatch: pytest.MonkeyPatch) -> str:
    pid = "BP-TEST123456-01"
    monkeypatch.setenv("BARION_PIXEL_ID", pid)
    return pid


def test_barion_pixel_markup_uses_const_loader_and_noscript(pixel_id: str) -> None:
    html = barion_pixel_markup(pixel_id)
    assert "Barion Base Pixel - required for Barion merchant approval" in html
    assert "const scriptElement = document.createElement" in html
    assert "const firstScript = document.getElementsByTagName" in html
    assert 'scriptElement.src = "https://pixel.barion.com/bp.js"' in html
    assert f"window['barion_pixel_id'] = '{pixel_id}'" in html
    assert "bp('init', 'addBarionPixelId', window['barion_pixel_id'])" in html
    assert f"ba_pixel_id={pixel_id}" in html
    assert "noscript" in html


def test_inject_replaces_slot(pixel_id: str) -> None:
    source = "<html><head><!-- BARION_PIXEL_SLOT --></head></html>"
    out = inject_barion_pixel(source)
    assert "<!-- BARION_PIXEL_SLOT -->" not in out
    assert pixel_id in out
    assert "pixel.barion.com/bp.js" in out


def test_inject_strips_slot_when_pixel_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BARION_PIXEL_ID", raising=False)
    source = "<html><head><!-- BARION_PIXEL_SLOT --></head></html>"
    out = inject_barion_pixel(source)
    assert "<!-- BARION_PIXEL_SLOT -->" not in out
    assert "pixel.barion.com" not in out


def test_inject_rejects_invalid_pixel_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_PIXEL_ID", "not-a-valid-id")
    out = inject_barion_pixel("<html><head><!-- BARION_PIXEL_SLOT --></head></html>")
    assert "pixel.barion.com" not in out


@pytest.mark.parametrize(
    "invalid_id",
    [
        "BPT-TEST123456-01",
        "BP-SHORT-01",
        "BP-TOO-LONG-PIXEL-01",
        "BP-TEST_23456-01",
        "BP-TEST123456-AA",
        "BP-TEST123456-1",
    ],
)
def test_inject_rejects_noncanonical_pixel_ids(
    monkeypatch: pytest.MonkeyPatch, invalid_id: str
) -> None:
    monkeypatch.setenv("BARION_PIXEL_ID", invalid_id)
    out = inject_barion_pixel("<html><head><!-- BARION_PIXEL_SLOT --></head></html>")
    assert "pixel.barion.com" not in out


def test_storefront_includes_pixel_when_configured(pixel_id: str) -> None:
    from mesencsi import app

    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        assert pixel_id in r.text
        assert "https://pixel.barion.com/bp.js" in r.text


def test_password_reset_pages_include_pixel_when_configured(pixel_id: str) -> None:
    from mesencsi import app

    with TestClient(app) as client:
        for path in ("/forgot-password.html", "/reset-password.html"):
            r = client.get(path)
            assert r.status_code == 200, path
            assert pixel_id in r.text
            assert "https://pixel.barion.com/bp.js" in r.text
            assert f"ba_pixel_id={pixel_id}" in r.text
            assert "bp('init', 'addBarionPixelId', window['barion_pixel_id'])" in r.text


def test_admin_pages_do_not_include_pixel(pixel_id: str) -> None:
    from mesencsi import app

    with TestClient(app) as client:
        r = client.get("/admin/login")
        assert r.status_code == 200
        assert pixel_id not in r.text
        assert "pixel.barion.com/bp.js" not in r.text


def test_startup_does_not_log_pixel_id(pixel_id: str, caplog: pytest.LogCaptureFixture) -> None:
    from mesencsi import app

    with caplog.at_level(logging.DEBUG), TestClient(app) as client:
        client.get("/")
    assert pixel_id not in caplog.text
