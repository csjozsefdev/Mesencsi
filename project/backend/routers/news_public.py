"""Publikus hírek — csak közzétett tartalom, login nélkül."""

from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comment_limits import enforce_news_comment_flood_guard
from database import get_db
from db_models import AppUser, NewsComment, NewsPost
from dependencies import require_email_verified_shop_user
from models import (
    NewsCommentCreate,
    NewsCommentPage,
    NewsCommentPublic,
    NewsListItemPublic,
    NewsPage,
    NewsPublicDetail,
)
from services import require_published_news_post

router = APIRouter(prefix="/news", tags=["news"])


def _published_filter():
    return NewsPost.is_published.is_(True)


def _visible_comment_count(db: Session, news_id: int) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(NewsComment)
            .where(
                NewsComment.news_id == news_id,
                NewsComment.is_visible.is_(True),
            )
        )
        or 0
    )


def _news_detail_with_count(db: Session, row: NewsPost) -> NewsPublicDetail:
    base = NewsPublicDetail.model_validate(row)
    return base.model_copy(update={"comment_count": _visible_comment_count(db, row.id)})


def _news_list_item_with_count(db: Session, row: NewsPost) -> NewsListItemPublic:
    base = NewsListItemPublic.model_validate(row)
    return base.model_copy(update={"comment_count": _visible_comment_count(db, row.id)})


@router.get("/featured", response_model=NewsPublicDetail | None)
def get_featured_news(db: Session = Depends(get_db)) -> NewsPublicDetail | None:
    """Kiemelt közzétett hír, vagy ha nincs, a legfrissebb közzétett."""
    stmt = (
        select(NewsPost)
        .where(_published_filter(), NewsPost.is_featured.is_(True))
        .order_by(NewsPost.published_at.desc().nulls_last(), NewsPost.id.desc())
        .limit(1)
    )
    row = db.scalars(stmt).first()
    if row is None:
        stmt2 = (
            select(NewsPost)
            .where(_published_filter())
            .order_by(NewsPost.published_at.desc().nulls_last(), NewsPost.id.desc())
            .limit(1)
        )
        row = db.scalars(stmt2).first()
    if row is None:
        return None
    return _news_detail_with_count(db, row)


@router.get("", response_model=NewsPage)
def list_published_news(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
) -> NewsPage:
    total = int(db.scalar(select(func.count()).select_from(NewsPost).where(_published_filter())) or 0)
    offset = (page - 1) * page_size
    stmt = (
        select(NewsPost)
        .where(_published_filter())
        .order_by(NewsPost.published_at.desc().nulls_last(), NewsPost.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = list(db.scalars(stmt).all())
    items = [_news_list_item_with_count(db, row) for row in rows]
    pages = ceil(total / page_size) if total and page_size else 0
    if total > 0 and page > pages:
        raise HTTPException(
            status_code=422,
            detail=f"Nincs ilyen oldal. Érvényes oldalak: 1–{pages}.",
        )
    if total == 0 and page > 1:
        raise HTTPException(status_code=422, detail="Még nincs közzétett hír — csak az 1. oldal létezik.")
    return NewsPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/slug/{slug}", response_model=NewsPublicDetail)
def get_published_news_by_slug(slug: str, db: Session = Depends(get_db)) -> NewsPublicDetail:
    row = db.scalars(
        select(NewsPost).where(NewsPost.slug == slug.strip(), _published_filter()).limit(1)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen közzétett hír.")
    return _news_detail_with_count(db, row)


def _author_for_public_comment(user: AppUser | None) -> tuple[str, str | None]:
    if user is None:
        return "Törölt felhasználó", None
    nick = (user.nickname or "").strip()
    name = nick or user.username
    av = (user.profile_image_url or "").strip() or None
    return name, av


def _author_for_public_comment_cols(
    *,
    user_id: int | None,
    username: str | None,
    nickname: str | None,
    profile_image_url: str | None,
) -> tuple[str, str | None]:
    """Same display rules as `_author_for_public_comment`, but without loading full AppUser rows."""
    if user_id is None:
        return "Törölt felhasználó", None
    nick = (nickname or "").strip()
    name = nick or (username or "").strip() or "Törölt felhasználó"
    av = (profile_image_url or "").strip() or None
    return name, av


@router.get("/{news_id}/comments", response_model=NewsCommentPage)
def list_visible_news_comments(
    news_id: int,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
) -> NewsCommentPage:
    """Csak látható kommentek, időrendben (legrégebbi felül — beszélgetőszerű)."""
    require_published_news_post(db, news_id)
    vis = (NewsComment.news_id == news_id) & (NewsComment.is_visible.is_(True))
    total = int(db.scalar(select(func.count()).select_from(NewsComment).where(vis)) or 0)
    offset = (page - 1) * page_size
    pages = ceil(total / page_size) if total and page_size else 0
    if total > 0 and page > pages:
        raise HTTPException(
            status_code=422,
            detail=f"Nincs ilyen oldal. Érvényes oldalak: 1–{pages}.",
        )
    if total == 0 and page > 1:
        raise HTTPException(status_code=422, detail="Ehhez a hírhez még nincs hozzászólás — csak az 1. oldal létezik.")
    stmt = (
        # IMPORTANT: Select only the public author fields. Do not load full AppUser rows here,
        # so the endpoint stays robust even if the users table schema is behind migrations.
        select(NewsComment, AppUser.username, AppUser.nickname, AppUser.profile_image_url)
        .outerjoin(AppUser, AppUser.id == NewsComment.user_id)
        .where(vis)
        .order_by(NewsComment.created_at.asc(), NewsComment.id.asc())
        .offset(offset)
        .limit(page_size)
    )
    rows = db.execute(stmt).all()
    items: list[NewsCommentPublic] = []
    for c, username, nickname, profile_image_url in rows:
        disp, av = _author_for_public_comment_cols(
            user_id=c.user_id,
            username=username,
            nickname=nickname,
            profile_image_url=profile_image_url,
        )
        items.append(
            NewsCommentPublic(
                id=c.id,
                content=c.content,
                created_at=c.created_at,
                author_display_name=disp,
                author_avatar_url=av,
            )
        )
    return NewsCommentPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/{news_id}/comments", response_model=NewsCommentPublic, status_code=status.HTTP_201_CREATED)
def create_news_comment(
    news_id: int,
    payload: NewsCommentCreate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_email_verified_shop_user),
) -> NewsCommentPublic:
    require_published_news_post(db, news_id)
    enforce_news_comment_flood_guard(db, user_id=user.id)
    row = NewsComment(
        news_id=news_id,
        user_id=user.id,
        content=payload.content,
        is_visible=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    disp, av = _author_for_public_comment(user)
    return NewsCommentPublic(
        id=row.id,
        content=row.content,
        created_at=row.created_at,
        author_display_name=disp,
        author_avatar_url=av,
    )


@router.get("/{news_id}", response_model=NewsPublicDetail)
def get_published_news_by_id(news_id: int, db: Session = Depends(get_db)) -> NewsPublicDetail:
    row = db.get(NewsPost, news_id)
    if row is None or not row.is_published:
        raise HTTPException(status_code=404, detail="Nincs ilyen közzétett hír.")
    return _news_detail_with_count(db, row)
