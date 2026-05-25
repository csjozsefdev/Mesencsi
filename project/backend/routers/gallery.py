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

_GALLERY_ORDER = (GalleryItem.sort_order.asc(), GalleryItem.id.asc())


def _paginate_displayable_ids(db: Session, *, offset: int, limit: int) -> tuple[int, list[int]]:
    """
    One ordered DB read (id + image_url columns only), then filesystem displayable filter.

    Returns (total_displayable_count, ids_for_requested_page). Page ids are collected in a
    single pass so we do not keep every displayable id in memory.
    """
    stmt = select(GalleryItem.id, GalleryItem.image_url).order_by(*_GALLERY_ORDER)
    total = 0
    page_ids: list[int] = []
    for row in db.execute(stmt):
        if not local_public_media_displayable(row[1]):
            continue
        if offset <= total < offset + limit:
            page_ids.append(int(row[0]))
        total += 1
    return total, page_ids


def _fetch_gallery_items_by_ids(db: Session, ids: list[int]) -> list[GalleryItem]:
    """Load one page of rows from Postgres; order matches the public gallery sort."""
    if not ids:
        return []
    rows = list(
        db.scalars(select(GalleryItem).where(GalleryItem.id.in_(ids)).order_by(*_GALLERY_ORDER)).all()
    )
    by_id = {int(r.id): r for r in rows}
    return [by_id[i] for i in ids if i in by_id]


@router.get("", response_model=GalleryPage)
def list_gallery(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="1-based page index"),
    page_size: int = Query(12, ge=1, le=100, description="Items per page (max 100)"),
) -> GalleryPage:
    offset = (page - 1) * page_size
    total, page_ids = _paginate_displayable_ids(db, offset=offset, limit=page_size)
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

    items = _fetch_gallery_items_by_ids(db, page_ids)

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
