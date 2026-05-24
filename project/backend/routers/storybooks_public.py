"""Publikus digitális mesekönyvek — csak közzétett tartalom."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from db_models import DigitalStorybook, DigitalStorybookPage
from models import StorybookListItemPublic, StorybookPagePublic, StorybookPublicDetail
from services import require_published_storybook_by_slug

router = APIRouter(prefix="/storybooks", tags=["storybooks"])

# Régi hibás kliensek: könyv-id és oldal egy szegmensben (pl. "3:1") — nem slug.
_LEGACY_ID_PAGE_SLUG = re.compile(r"^\d+:\d+$")


def _published_filter():
    return DigitalStorybook.is_published.is_(True)


@router.get("", response_model=list[StorybookListItemPublic])
def list_published_storybooks(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(DigitalStorybook)
        .where(_published_filter())
        .order_by(DigitalStorybook.updated_at.desc(), DigitalStorybook.id.desc())
    ).all()
    return list(rows)


@router.get("/{slug}", response_model=StorybookPublicDetail)
def get_published_storybook(slug: str, db: Session = Depends(get_db)):
    raw = (slug or "").strip()
    if _LEGACY_ID_PAGE_SLUG.fullmatch(raw):
        raise HTTPException(
            status_code=400,
            detail=(
                "Érvénytelen mesekönyv URL: a könyv azonosítója és az oldalszám ne legyen egyetlen "
                "path szegmensben (pl. 3:1). Használd a könyv slugját: /storybooks/{slug}."
            ),
        )
    book = require_published_storybook_by_slug(db, raw)
    pages = list(
        db.scalars(
            select(DigitalStorybookPage)
            .where(DigitalStorybookPage.book_id == book.id)
            .order_by(DigitalStorybookPage.page_index.asc(), DigitalStorybookPage.id.asc())
        ).all()
    )
    try:
        pub_pages = [StorybookPagePublic.model_validate(p) for p in pages]
        anim = book.animation_settings
        if not isinstance(anim, dict):
            anim = {}
        return StorybookPublicDetail(
            id=book.id,
            slug=book.slug,
            title=book.title,
            description=book.description,
            cover_image_url=book.cover_image_url,
            animation_settings=anim,
            updated_at=book.updated_at,
            pages=pub_pages,
        )
    except ValidationError:
        raise HTTPException(
            status_code=422,
            detail="A mesekönyv tárolt adatai nem értelmezhetők (sérült vagy inkompatibilis mezők).",
        ) from None
