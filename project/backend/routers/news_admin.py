"""Admin hírek — admin JWT (owner / maintenance), írás: owner."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from database import get_db
from db_models import NewsPost
from dependencies import CurrentAdmin, require_role
from image_upload import delete_uploaded_file_by_url, save_uploaded_image
from models import (
    AdminImageUploadResponse,
    NewsCreate,
    NewsFeatureUpdate,
    NewsPublishUpdate,
    NewsRead,
    NewsUpdate,
)
from news_slug import allocate_unique_slug, slugify_title
from services import find_news_post

router = APIRouter(prefix="/news", tags=["admin-news"])


def _clear_other_featured(db: Session, keep_id: int) -> None:
    db.execute(update(NewsPost).where(NewsPost.id != keep_id).values(is_featured=False))


@router.get("", response_model=list[NewsRead])
def admin_list_news(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    return list(
        db.scalars(select(NewsPost).order_by(NewsPost.created_at.desc(), NewsPost.id.desc())).all()
    )


@router.post("", response_model=NewsRead, status_code=201)
def admin_create_news(
    payload: NewsCreate,
    db: Session = Depends(get_db),
    admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    slug_src = (payload.slug or "").strip()
    base_slug = slugify_title(slug_src) if slug_src else slugify_title(payload.title)
    slug = allocate_unique_slug(db, base_slug)
    published_at = datetime.now(UTC) if payload.is_published else None
    if payload.is_featured:
        db.execute(update(NewsPost).values(is_featured=False))
    row = NewsPost(
        title=payload.title.strip(),
        slug=slug,
        summary=payload.summary.strip(),
        body=payload.body.strip(),
        image_url=None,
        is_published=payload.is_published,
        is_featured=payload.is_featured,
        release_event_at=payload.release_event_at,
        published_at=published_at,
        author_username=admin.username,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{news_id}", response_model=NewsRead)
def admin_update_news(
    news_id: int,
    payload: NewsUpdate,
    db: Session = Depends(get_db),
    admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_news_post(db, news_id)
    if payload.title is not None:
        row.title = payload.title.strip()
    if payload.summary is not None:
        row.summary = payload.summary.strip()
    if payload.body is not None:
        row.body = payload.body.strip()
    if payload.release_event_at is not None:
        row.release_event_at = payload.release_event_at

    if payload.slug is not None:
        base = slugify_title(payload.slug)
        row.slug = allocate_unique_slug(db, base, exclude_id=row.id)

    if payload.is_published is not None:
        if payload.is_published and not row.is_published:
            row.published_at = datetime.now(UTC)
        elif not payload.is_published:
            row.published_at = None
        row.is_published = payload.is_published

    if payload.is_featured is not None:
        if payload.is_featured:
            _clear_other_featured(db, row.id)
            row.is_featured = True
        else:
            row.is_featured = False

    row.author_username = admin.username
    db.commit()
    db.refresh(row)
    return row


@router.post("/{news_id}/image", response_model=AdminImageUploadResponse)
async def admin_upload_news_image(
    news_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_news_post(db, news_id)
    prev = row.image_url
    url, filename = await save_uploaded_image(file, subdir="news", filename_prefix=f"news-{news_id}")
    row.image_url = url
    db.commit()
    if prev and prev.strip() != url.strip():
        delete_uploaded_file_by_url(prev)
    return AdminImageUploadResponse(url=url, filename=filename)


@router.delete("/{news_id}", status_code=204)
def admin_delete_news(
    news_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_news_post(db, news_id)
    img = row.image_url
    db.delete(row)
    db.commit()
    delete_uploaded_file_by_url(img)
    return None


@router.patch("/{news_id}/publish", response_model=NewsRead)
def admin_publish_news(
    news_id: int,
    payload: NewsPublishUpdate,
    db: Session = Depends(get_db),
    admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_news_post(db, news_id)
    if payload.is_published:
        if not row.is_published:
            row.published_at = datetime.now(UTC)
        row.is_published = True
    else:
        row.is_published = False
        row.published_at = None
    row.author_username = admin.username
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{news_id}/feature", response_model=NewsRead)
def admin_feature_news(
    news_id: int,
    payload: NewsFeatureUpdate,
    db: Session = Depends(get_db),
    admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_news_post(db, news_id)
    if payload.is_featured:
        _clear_other_featured(db, row.id)
        row.is_featured = True
    else:
        row.is_featured = False
    row.author_username = admin.username
    db.commit()
    db.refresh(row)
    return row
