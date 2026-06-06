"""Admin: hírkommentek moderálása (lista, láthatóság, törlés).

Note: this router is not mounted in mesencsi.py yet. Comment moderation models exist;
wire via admin_routes when the admin UI is ready.
"""

from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from db_models import AppUser, NewsComment, NewsPost
from dependencies import CurrentAdmin, require_role
from models import AdminNewsCommentPage, AdminNewsCommentRead, NewsCommentVisibilityPatch

router = APIRouter(prefix="/comments", tags=["admin-comments"])


def _serialize_admin_comment(
    c: NewsComment,
    post: NewsPost,
    user: AppUser | None,
) -> AdminNewsCommentRead:
    return AdminNewsCommentRead(
        id=c.id,
        news_id=c.news_id,
        news_title=post.title,
        user_id=c.user_id,
        user_email=user.email if user else None,
        content=c.content,
        is_visible=c.is_visible,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=AdminNewsCommentPage)
def admin_list_news_comments(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    news_id: int | None = Query(None, description="Szűrés egy adott hírre."),
) -> AdminNewsCommentPage:
    cq = select(func.count()).select_from(NewsComment).join(NewsPost, NewsPost.id == NewsComment.news_id)
    if news_id is not None:
        cq = cq.where(NewsComment.news_id == news_id)
    total = int(db.scalar(cq) or 0)

    offset = (page - 1) * page_size
    pages = ceil(total / page_size) if total and page_size else 0
    if total > 0 and page > pages:
        raise HTTPException(
            status_code=422,
            detail=f"Nincs ilyen oldal. Érvényes oldalak: 1–{pages}.",
        )
    if total == 0 and page > 1:
        raise HTTPException(status_code=422, detail="Még nincs egyetlen hozzászólás sem — csak az 1. oldal létezik.")

    stmt = (
        select(NewsComment, NewsPost, AppUser)
        .join(NewsPost, NewsPost.id == NewsComment.news_id)
        .outerjoin(AppUser, AppUser.id == NewsComment.user_id)
    )
    if news_id is not None:
        stmt = stmt.where(NewsComment.news_id == news_id)
    stmt = stmt.order_by(NewsComment.created_at.desc(), NewsComment.id.desc()).offset(offset).limit(page_size)
    rows = db.execute(stmt).all()
    items = [_serialize_admin_comment(c, p, u) for c, p, u in rows]
    return AdminNewsCommentPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.patch("/{comment_id}/visibility", response_model=AdminNewsCommentRead)
def admin_patch_comment_visibility(
    comment_id: int,
    payload: NewsCommentVisibilityPatch,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
) -> AdminNewsCommentRead:
    row = db.get(NewsComment, comment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen hozzászólás.")
    row.is_visible = payload.is_visible
    db.commit()
    db.refresh(row)
    post = db.get(NewsPost, row.news_id)
    if post is None:
        raise HTTPException(status_code=404, detail="A hír nem található.")
    user = db.get(AppUser, row.user_id) if row.user_id is not None else None
    return _serialize_admin_comment(row, post, user)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_news_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
) -> None:
    row = db.get(NewsComment, comment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen hozzászólás.")
    db.delete(row)
    db.commit()
    return None
