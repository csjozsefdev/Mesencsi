"""URL-barát slug a hír címéből + egyediség ellenőrzés a DB-ben."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from db_models import NewsPost


def slugify_title(title: str) -> str:
    s = unicodedata.normalize("NFKD", title.strip())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return (s[:200] if s else "hir")


def allocate_unique_slug(db: Session, base: str, *, exclude_id: int | None = None) -> str:
    stem = (base or "hir").strip().lower()[:200] or "hir"
    candidate = stem
    n = 2
    while True:
        q = select(NewsPost.id).where(NewsPost.slug == candidate)
        if exclude_id is not None:
            q = q.where(NewsPost.id != exclude_id)
        if db.scalar(q) is None:
            return candidate[:255]
        suffix = f"-{n}"
        candidate = (stem[: 255 - len(suffix)] + suffix)[:255]
        n += 1
