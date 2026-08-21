#!/usr/bin/env python3
"""
Read-only audit: find existing storybook pages that exceed the new safe
character limits introduced by the page-layout redesign (image_placement,
no more automatic vignette/hero split).

Reuses the backend's own DB configuration (``database.SessionLocal``) — no
credentials are requested, read, or printed by this script. Performs
SELECT-only queries. Does not modify anything and does not truncate any text
— it only reports which pages a human should review/shorten.

A page is flagged only if it is in "simple" (non-custom-layout) mode — pages
using the free-position drag/resize system are unrestricted by design and are
skipped, matching pageHasCustomImageLayout/pageHasCustomDragPos in
storybook-reader.js and _page_uses_custom_layout() in storybooks_admin.py.

Usage (run from project/backend, with the same interpreter/venv the app uses):
    python scripts/audit_storybook_page_text_limits.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from database import SessionLocal  # noqa: E402
from db_models import DigitalStorybook, DigitalStorybookPage  # noqa: E402
from models import (  # noqa: E402
    STORYBOOK_TEXT_ONLY_MAX_CHARS,
    STORYBOOK_TEXT_WITH_IMAGE_MAX_CHARS,
)


def _uses_custom_layout(page: DigitalStorybookPage) -> bool:
    has_custom_image = (
        page.image_x_percent is not None
        and page.image_y_percent is not None
        and page.image_width_percent is not None
    )
    has_custom_text = page.text_x_percent is not None and page.text_y_percent is not None
    return has_custom_image or has_custom_text


def main() -> int:
    db = SessionLocal()
    try:
        books = {b.id: b for b in db.scalars(select(DigitalStorybook)).all()}
        pages = list(
            db.scalars(
                select(DigitalStorybookPage).order_by(
                    DigitalStorybookPage.book_id.asc(), DigitalStorybookPage.page_index.asc()
                )
            ).all()
        )

        flagged = []
        skipped_advanced = 0
        for p in pages:
            if _uses_custom_layout(p):
                skipped_advanced += 1
                continue
            limit = STORYBOOK_TEXT_WITH_IMAGE_MAX_CHARS if p.image_url else STORYBOOK_TEXT_ONLY_MAX_CHARS
            length = len(p.body_text or "")
            if length > limit:
                flagged.append((p, limit, length))

        print(f"Scanned {len(pages)} pages across {len(books)} storybooks.")
        print(f"Skipped {skipped_advanced} page(s) using the free-position (advanced) layout — unrestricted by design.")
        print()

        if not flagged:
            print("No pages exceed the new safe limits. Nothing to review.")
            return 0

        print(f"{len(flagged)} page(s) exceed the new safe limit and should be reviewed/shortened:")
        print("=" * 72)
        for p, limit, length in flagged:
            book = books.get(p.book_id)
            title = book.title if book else "?"
            slug = book.slug if book else "?"
            has_image = bool(p.image_url)
            print(f"- book id={p.book_id} slug={slug!r} title={title!r}")
            print(f"  page id={p.id} page_index={p.page_index}")
            print(f"  has_image={has_image} limit={limit} current_length={length} (over by {length - limit})")
            print()

        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
