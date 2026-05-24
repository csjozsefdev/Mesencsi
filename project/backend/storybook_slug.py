"""Digitális storybook slug — hírhez hasonló egyediség a ``digital_storybooks`` táblán."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from db_models import DigitalStorybook
from news_slug import slugify_title


def allocate_unique_storybook_slug(db: Session, base: str, *, exclude_id: int | None = None) -> str:
    stem = slugify_title(base)[:200] or "storybook"
    candidate = stem
    n = 2
    while True:
        q = select(DigitalStorybook.id).where(DigitalStorybook.slug == candidate)
        if exclude_id is not None:
            q = q.where(DigitalStorybook.id != exclude_id)
        if db.scalar(q) is None:
            return candidate[:255]
        suffix = f"-{n}"
        candidate = (stem[: 255 - len(suffix)] + suffix)[:255]
        n += 1
