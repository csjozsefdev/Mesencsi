"""Paginated gallery (images / cards) backed by ``gallery_items`` in Postgres."""

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from db_models import GalleryItem
from image_upload import local_public_media_displayable
from models import GalleryItemRead, GalleryPage

router = APIRouter(prefix="/gallery", tags=["gallery"])


def _public_gallery_rows(db: Session) -> list[GalleryItem]:
    """Rows with a real on-disk image (skips missing files and tiny empty placeholders)."""
    stmt = select(GalleryItem).order_by(GalleryItem.sort_order.asc(), GalleryItem.id.asc())
    rows = list(db.scalars(stmt).all())
    return [r for r in rows if local_public_media_displayable(r.image_url)]


@router.get("", response_model=GalleryPage)
def list_gallery(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="1-based page index"),
    page_size: int = Query(12, ge=1, le=100, description="Items per page (max 100)"),
) -> GalleryPage:
    visible = _public_gallery_rows(db)
    total = len(visible)
    offset = (page - 1) * page_size
    items = visible[offset : offset + page_size]
    pages = ceil(total / page_size) if total and page_size else 0

    if total > 0 and page > pages:
        raise HTTPException(
            status_code=422,
            detail=f"Nincs ilyen oldal a galériában. Érvényes oldalak: 1–{pages}.",
        )
    if total == 0 and page > 1:
        raise HTTPException(
            status_code=422,
            detail="Még nincs galériakép — csak az 1. oldal létezik.",
        )

    return GalleryPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{item_id}", response_model=GalleryItemRead)
def get_gallery_item(item_id: int, db: Session = Depends(get_db)) -> GalleryItem:
    row = db.get(GalleryItem, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen galériakép.")
    return row
