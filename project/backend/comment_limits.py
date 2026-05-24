"""Egyszerű flood / cooldown védelem hírkommentekhez (DB-alapú, worker-barát)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db_models import NewsComment

# Minimális „emberi” szünet két komment között (másodperc).
_COOLDOWN_SECONDS = 25
# Időablakon belüli max kommentek száma / user (globálisan minden hírre).
_WINDOW_MINUTES = 10
_MAX_COMMENTS_IN_WINDOW = 8


def _to_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def enforce_news_comment_flood_guard(db: Session, *, user_id: int) -> None:
    """Túl gyakori vagy túl sűrű kommentelés: 429."""
    now = datetime.now(UTC)
    last_any = db.scalar(select(func.max(NewsComment.created_at)).where(NewsComment.user_id == user_id))
    if last_any is not None:
        last_any = _to_utc_aware(last_any)
        elapsed = (now - last_any).total_seconds()
        if elapsed < _COOLDOWN_SECONDS:
            wait = int(_COOLDOWN_SECONDS - elapsed) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Túl gyorsan küldesz hozzászólást. Várj még kb. {wait} másodpercet.",
            )
    since = now - timedelta(minutes=_WINDOW_MINUTES)
    cnt = int(
        db.scalar(
            select(func.count())
            .select_from(NewsComment)
            .where(NewsComment.user_id == user_id, NewsComment.created_at >= since)
        )
        or 0
    )
    if cnt >= _MAX_COMMENTS_IN_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Legfeljebb {_MAX_COMMENTS_IN_WINDOW} hozzászólást küldhetsz {_WINDOW_MINUTES} perc alatt. Próbáld újra később.",
        )
