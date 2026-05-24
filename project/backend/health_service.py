"""Olcsó health ellenőrzések — business health nem tartalmaz titkokat."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from auth import create_admin_token, decode_admin_token
from barion_api import barion_sandbox_mode
from frontend_assets import page_background_asset_ok
from image_upload import UPLOADS_ROOT

_BACKEND_DIR = Path(__file__).resolve().parent
_FRONTEND_DIR = (_BACKEND_DIR.parent / "frontend").resolve()
_MEDIA_UPLOAD_DIR = UPLOADS_ROOT

_CORE_TABLES = ("users", "orders", "products", "login_throttle")


def environment_name() -> str:
    return (os.environ.get("ENVIRONMENT") or os.environ.get("ENV") or "development").strip()


def lightweight_health_payload() -> dict:
    return {
        "status": "ok",
        "app": "mesencsi",
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": environment_name(),
    }


def _dir_writable_ok(directory: Path) -> tuple[bool, str]:
    try:
        p = directory.resolve()
        if not p.is_dir():
            return False, "missing"
        probe = p / ".health_write_probe"
        try:
            probe.write_text("", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True, "ok"
        except OSError:
            return False, "not_writable"
    except OSError:
        return False, "error"


def _frontend_static_ok() -> tuple[bool, str]:
    try:
        p = _FRONTEND_DIR.resolve()
        if not p.is_dir():
            return False, "missing"
        if not (p / "mesencsi.html").is_file():
            return False, "incomplete"
        if not page_background_asset_ok():
            return False, "missing_bg_asset"
        return True, "ok"
    except OSError:
        return False, "error"


def _media_uploads_ok() -> tuple[bool, str]:
    return _dir_writable_ok(_MEDIA_UPLOAD_DIR)


def _barion_summary() -> dict:
    sandbox = barion_sandbox_mode()
    pos_key = bool((os.environ.get("BARION_POS_KEY") or "").strip())
    pos_id = bool((os.environ.get("BARION_POS_ID") or "").strip())
    env_raw = (os.environ.get("BARION_ENV") or "").strip()
    return {
        "barion_env": env_raw or None,
        "sandbox_mode": sandbox,
        "pos_key_configured": pos_key,
        "pos_id_configured": pos_id,
        "rest_api_ready": pos_key,
    }


def _email_summary() -> dict:
    host = os.environ.get("SMTP_HOST", "").strip()
    return {"smtp_configured": bool(host), "mode": "smtp" if host else "log_only"}


def _admin_auth_roundtrip_ok() -> bool:
    try:
        tok = create_admin_token(username="health_probe", role="maintenance")
        u, r = decode_admin_token(tok)
        return u == "health_probe" and r == "maintenance"
    except Exception:
        return False


def run_business_health(db: Session) -> dict:
    """Egy DB ping + egy information_schema lekérdezés + fájlrendszer / env jelzők."""
    checked_at = datetime.now(UTC).isoformat()
    env = environment_name()
    overall = "ok"
    db_ms: float | None = None
    db_ok = False
    tables: dict[str, bool] = dict.fromkeys(_CORE_TABLES, False)

    t0 = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        db_ms = round((time.perf_counter() - t0) * 1000, 2)
        db_ok = True
    except Exception:
        overall = "degraded"
        db_ms = None

    if db_ok:
        try:
            stmt = text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name IN :names"
            ).bindparams(bindparam("names", expanding=True))
            found = {row[0] for row in db.execute(stmt, {"names": list(_CORE_TABLES)}).all()}
            for t in _CORE_TABLES:
                tables[t] = t in found
            if not all(tables.values()):
                overall = "degraded"
        except Exception:
            overall = "degraded"
            tables = dict.fromkeys(_CORE_TABLES, False)

    frontend_ok, frontend_detail = _frontend_static_ok()
    media_ok, media_detail = _media_uploads_ok()
    if not frontend_ok or not media_ok:
        overall = "degraded"

    admin_probe = _admin_auth_roundtrip_ok()
    if not admin_probe:
        overall = "degraded"

    return {
        "status": overall,
        "checked_at": checked_at,
        "environment": env,
        "components": {
            "database": {"ok": db_ok, "latency_ms": db_ms},
            "core_tables": tables,
            "admin_auth_token_roundtrip": admin_probe,
            "orders_table_ready": tables.get("orders", False),
            "users_table_ready": tables.get("users", False),
            "static_frontend": {"ok": frontend_ok, "detail": frontend_detail, "path_hint": "frontend"},
            "media_uploads": {"ok": media_ok, "detail": media_detail, "path_hint": "media/uploads"},
            "barion": _barion_summary(),
            "email": _email_summary(),
        },
    }
