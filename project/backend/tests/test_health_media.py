"""Health media / static path checks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from health_service import (
    _dir_writable_ok,
    _frontend_static_ok,
    _media_uploads_ok,
    run_business_health,
)


def test_dir_writable_ok_on_temp_dir(tmp_path: Path):
    ok, detail = _dir_writable_ok(tmp_path)
    assert ok is True
    assert detail == "ok"


def test_dir_writable_ok_missing_dir(tmp_path: Path):
    missing = tmp_path / "nope"
    ok, detail = _dir_writable_ok(missing)
    assert ok is False
    assert detail == "missing"


def test_dir_writable_ok_not_writable(tmp_path: Path):
    def deny_write(self, *args, **kwargs):
        if self.name == ".health_write_probe":
            raise OSError("permission denied")
        return Path.write_text(self, *args, **kwargs)

    with patch.object(Path, "write_text", deny_write):
        ok, detail = _dir_writable_ok(tmp_path)
    assert ok is False
    assert detail == "not_writable"


def test_media_uploads_ok_uses_backend_uploads_root():
    ok, detail = _media_uploads_ok()
    assert ok is True
    assert detail == "ok"


def test_frontend_static_ok():
    ok, detail = _frontend_static_ok()
    assert ok is True
    assert detail == "ok"


def test_frontend_static_missing_bg(monkeypatch):
    monkeypatch.setattr("health_service.page_background_asset_ok", lambda: False)
    ok, detail = _frontend_static_ok()
    assert ok is False
    assert detail == "missing_bg_asset"


def test_frontend_static_incomplete(tmp_path: Path, monkeypatch):
    empty_frontend = tmp_path / "frontend"
    empty_frontend.mkdir()
    monkeypatch.setattr("health_service._FRONTEND_DIR", empty_frontend)
    ok, detail = _frontend_static_ok()
    assert ok is False
    assert detail == "incomplete"


def test_business_health_exposes_split_frontend_and_media_checks():
    from database import SessionLocal

    db = SessionLocal()
    try:
        payload = run_business_health(db)
    finally:
        db.close()
    comps = payload["components"]
    assert comps["static_frontend"] == {"ok": True, "detail": "ok", "path_hint": "frontend"}
    assert comps["media_uploads"] == {"ok": True, "detail": "ok", "path_hint": "media/uploads"}
    assert "media_upload_dir" not in comps


def test_business_health_degraded_when_media_missing(monkeypatch, tmp_path: Path):
    from database import SessionLocal

    monkeypatch.setattr("health_service._MEDIA_UPLOAD_DIR", tmp_path / "missing_uploads")
    db = SessionLocal()
    try:
        payload = run_business_health(db)
    finally:
        db.close()
    assert payload["status"] == "degraded"
    assert payload["components"]["media_uploads"] == {
        "ok": False,
        "detail": "missing",
        "path_hint": "media/uploads",
    }