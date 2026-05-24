"""Check storefront assets: ``frontend/images/mesencsi-bg.jpg`` (project file) + favicons.

Background is never generated — place ``mesencsi-bg.jpg`` in ``frontend/images/`` yourself.
Favicons: ``python scripts/gen_mesencsi_favicons.py`` if ``favicon.ico`` is missing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"
GEN_FAVICONS = BACKEND / "scripts" / "gen_mesencsi_favicons.py"
BG_JPG = FRONTEND / "images" / "mesencsi-bg.jpg"
FAVICON = FRONTEND / "favicon.ico"


def page_background_present() -> bool:
    try:
        return BG_JPG.is_file() and BG_JPG.stat().st_size > 0
    except OSError:
        return False


def favicons_present() -> bool:
    try:
        return FAVICON.is_file() and FAVICON.stat().st_size > 0
    except OSError:
        return False


def ensure_frontend_assets() -> bool:
    ok = True
    if not page_background_present():
        print(
            f"ERROR: Missing page background — add your image at:\n  {BG_JPG}",
            file=sys.stderr,
        )
        ok = False
    if not favicons_present():
        if not GEN_FAVICONS.is_file():
            print("ERROR: gen script missing:", GEN_FAVICONS, file=sys.stderr)
            ok = False
        else:
            print("Missing favicon.ico — running gen_mesencsi_favicons.py ...")
            r = subprocess.run([sys.executable, str(GEN_FAVICONS)], cwd=str(BACKEND))
            if r.returncode != 0 or not favicons_present():
                print("ERROR: favicon generation failed.", file=sys.stderr)
                ok = False
    if ok:
        print("OK: storefront assets (mesencsi-bg.jpg + favicons).")
    return ok


if __name__ == "__main__":
    sys.exit(0 if ensure_frontend_assets() else 1)
