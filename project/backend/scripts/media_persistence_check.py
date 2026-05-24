#!/usr/bin/env python3
"""Media uploads könyvtár létezik és írható — lásd docs/media_persistence_smoke.md."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from health_service import _dir_writable_ok  # noqa: E402
from image_upload import UPLOADS_ROOT  # noqa: E402


def main() -> int:
    ok, detail = _dir_writable_ok(UPLOADS_ROOT)
    print(f"uploads_root={UPLOADS_ROOT}")
    print(f"writable={ok} detail={detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
