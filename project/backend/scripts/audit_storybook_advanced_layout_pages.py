#!/usr/bin/env python3
"""
Read-only audit: find storybook pages currently in "advanced" free-position
layout mode (image_x_percent/image_y_percent/image_width_percent all set —
the same predicate as pageHasCustomImageLayout() in storybook-reader.js and
_page_uses_custom_layout() in storybooks_admin.py), and flag which of those
look like they were never intentionally positioned by a human.

Why this matters: pages in this mode are dispatched to the old free-position
canvas renderer regardless of the new image_placement redesign — this is by
design (the owner chose to keep free-position as an unrestricted "advanced"
escape hatch). But a bug in the OLD admin editor (fixed this session, forward
only) could silently flip a page into this mode just by opening it with an
image visible and typing anywhere — without the admin ever touching the drag
handles. The old JS default was sbDefaultImageLayout() = {x:10, y:6, w:80,
h:34} — pages whose stored percent values closely match that exact default
are the prime suspects for "stuck by the old bug" rather than "deliberately
positioned by the owner."

Reuses the backend's own DB configuration (``database.SessionLocal``) — no
credentials are requested, read, or printed by this script. Performs
SELECT-only queries. Does not modify anything.

Usage (run from project/backend, with the same interpreter/venv the app uses):
    python scripts/audit_storybook_advanced_layout_pages.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from database import SessionLocal  # noqa: E402
from db_models import DigitalStorybook, DigitalStorybookPage  # noqa: E402

# The old admin JS's sbDefaultImageLayout() — never a value a human would type by hand.
_OLD_DEFAULT = {"x": 10.0, "y": 6.0, "w": 80.0, "h": 34.0}
_TOL = 0.5


def _close(a: float | None, b: float) -> bool:
    return a is not None and abs(a - b) <= _TOL


def main() -> int:
    db = SessionLocal()
    try:
        books = {b.id: b for b in db.scalars(select(DigitalStorybook)).all()}
        pages = list(
            db.scalars(
                select(DigitalStorybookPage)
                .where(
                    DigitalStorybookPage.image_x_percent.is_not(None),
                    DigitalStorybookPage.image_y_percent.is_not(None),
                    DigitalStorybookPage.image_width_percent.is_not(None),
                )
                .order_by(DigitalStorybookPage.book_id.asc(), DigitalStorybookPage.page_index.asc())
            ).all()
        )

        print(f"{len(pages)} page(s) currently in advanced/custom image-layout mode.")
        if not pages:
            print("Nothing to review.")
            return 0

        print("=" * 72)
        suspects = 0
        for p in pages:
            book = books.get(p.book_id)
            title = book.title if book else "?"
            slug = book.slug if book else "?"
            looks_default = (
                _close(p.image_x_percent, _OLD_DEFAULT["x"])
                and _close(p.image_y_percent, _OLD_DEFAULT["y"])
                and _close(p.image_width_percent, _OLD_DEFAULT["w"])
            )
            if looks_default:
                suspects += 1
            print(f"- book id={p.book_id} slug={slug!r} title={title!r}")
            print(f"  page id={p.id} page_index={p.page_index}")
            print(
                f"  image_x_percent={p.image_x_percent} image_y_percent={p.image_y_percent} "
                f"image_width_percent={p.image_width_percent} image_height_percent={p.image_height_percent}"
            )
            print(f"  SUSPECT (matches old accidental default): {looks_default}")
            print()

        print("=" * 72)
        print(f"{suspects} of {len(pages)} page(s) match the old accidental-default fingerprint.")
        print("These are candidates for a reviewed data reset (image_x/y/width/height_percent -> NULL)")
        print("to return them to the new simple/safe placement system — do not reset anything without")
        print("reviewing this list with the owner first.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
