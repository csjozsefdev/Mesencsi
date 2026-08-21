#!/usr/bin/env python3
"""
Read-only diagnostic: report a storybook's cover vs. its pages' image/audio URLs.

Reuses the backend's own DB configuration (``database.SessionLocal``, built from
the same .env / POSTGRES_* settings the running app uses) — no credentials are
requested, read, or printed by this script.

Performs SELECT-only queries. Does not INSERT/UPDATE/DELETE anything, and does
not touch any files on disk.

Usage (run from project/backend, with the same interpreter/venv the app uses):
    python scripts/report_storybook_cover_vs_pages.py "Dongó meséje"

If no title is given, it defaults to "Dongó meséje". Matching is case-insensitive
and trims surrounding whitespace. If zero or more than one storybook matches, it
lists the candidates it found instead of guessing.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import func, select  # noqa: E402

from database import SessionLocal  # noqa: E402
from db_models import DigitalStorybook, DigitalStorybookPage  # noqa: E402

DEFAULT_TITLE = "Dongó meséje"


def _norm(s: str | None) -> str:
    return (s or "").strip()


def _is_empty(s: str | None) -> bool:
    return not _norm(s)


def main() -> int:
    title = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TITLE
    wanted = _norm(title).lower()

    db = SessionLocal()
    try:
        candidates = list(
            db.scalars(
                select(DigitalStorybook).where(func.lower(func.trim(DigitalStorybook.title)) == wanted)
            ).all()
        )

        if not candidates:
            print(f'No storybook found with title == "{title}" (case/whitespace-insensitive).')
            print("Closest titles in the DB (for reference, no data changed):")
            all_titles = db.scalars(
                select(DigitalStorybook.title).order_by(DigitalStorybook.id.asc())
            ).all()
            for t in all_titles:
                print(f"  - {t!r}")
            return 1

        if len(candidates) > 1:
            print(f'Multiple storybooks match title "{title}" — refusing to guess which one:')
            for b in candidates:
                print(f"  - id={b.id} slug={b.slug!r} title={b.title!r}")
            return 1

        book = candidates[0]
        cover = _norm(book.cover_image_url) or None

        print("=" * 72)
        print("STORYBOOK")
        print("=" * 72)
        print(f"id               = {book.id}")
        print(f"title            = {book.title!r}")
        print(f"slug             = {book.slug!r}")
        print(f"is_published     = {book.is_published}")
        print(f"cover_image_url  = {cover!r}")
        print()

        pages = list(
            db.scalars(
                select(DigitalStorybookPage)
                .where(DigitalStorybookPage.book_id == book.id)
                .order_by(DigitalStorybookPage.page_index.asc(), DigitalStorybookPage.id.asc())
            ).all()
        )

        print("=" * 72)
        print(f"PAGES ({len(pages)})")
        print("=" * 72)
        if not pages:
            print("(no pages)")
            return 0

        for p in pages:
            img = _norm(p.image_url) or None
            aud = _norm(p.audio_url) or None
            img_empty = _is_empty(p.image_url)
            img_eq_cover = bool(img and cover and img == cover)
            print(f"- page id       = {p.id}")
            print(f"  page_index    = {p.page_index}")
            print(f"  image_url     = {img!r}")
            print(f"  audio_url     = {aud!r}")
            print(f"  image_empty   = {img_empty}")
            print(f"  image_eq_cover= {img_eq_cover}")
            print()

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
