"""Storefront page background — ``frontend/images/mesencsi-bg.jpg`` (project asset, never auto-generated)."""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger("mesencsi.frontend_assets")

_BACKEND = Path(__file__).resolve().parent
_FRONTEND = _BACKEND.parent / "frontend"
_BG_JPG = _FRONTEND / "images" / "mesencsi-bg.jpg"


def page_background_asset_path() -> Path:
    return _BG_JPG


def page_background_asset_ok() -> bool:
    try:
        return _BG_JPG.is_file() and _BG_JPG.stat().st_size > 0
    except OSError:
        return False


def ensure_page_background_at_startup() -> None:
    if page_background_asset_ok():
        return
    _log.warning(
        "Page background missing — add frontend/images/mesencsi-bg.jpg (not auto-generated). Expected: %s",
        _BG_JPG,
    )
