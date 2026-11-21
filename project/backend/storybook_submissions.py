"""Nyitási akció: regisztrált felhasználók mesekönyv-piszkozatai (beküldés az adminnak).

Az egész funkció a ``USER_STORYBOOKS_ENABLED`` környezeti változóval kapcsolható. Ha ki van
kapcsolva, a ``/my/storybooks`` végpontok 404-et adnak, a már beküldött anyagokat az admin
továbbra is kezelheti. A publikálás kizárólag az admin dolga: a felhasználói API sosem fogad
és sosem állít ``is_published`` értéket.

Az új tábla (``user_storybook_submissions``) a meglévő táblákhoz nem nyúl. A kapcsoló
leállítása után a tábla és az adatok érintetlenül maradnak.
"""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, inspect
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, engine

AUTHOR_MARKER = "Szerző: "

STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"

CONSENT_VERSION = "2026-11-promo-1"


class UserStorybookSubmission(Base):
    """Egy felhasználói mesekönyv tulajdonosa + beküldési állapota (digital_storybooks 1:1)."""

    __tablename__ = "user_storybook_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("digital_storybooks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=STATUS_DRAFT, index=True)
    author_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def ensure_submissions_table() -> None:
    """Az Alembic állapota a szerveren nem biztos, ezért a tábla hiányában létrehozzuk."""
    if not inspect(engine).has_table(UserStorybookSubmission.__tablename__):
        UserStorybookSubmission.__table__.create(bind=engine, checkfirst=True)


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int((os.getenv(name) or "").strip() or default)
    except ValueError:
        v = default
    return max(lo, min(hi, v))


def user_storybooks_enabled() -> bool:
    return (os.getenv("USER_STORYBOOKS_ENABLED") or "").strip().lower() in {"1", "true", "yes", "on"}


def max_open_books() -> int:
    return _env_int("USER_STORYBOOKS_MAX_BOOKS", 3, 1, 50)


def max_pages_per_book() -> int:
    return _env_int("USER_STORYBOOKS_MAX_PAGES", 20, 1, 200)


def split_author_marker(description: str | None) -> tuple[str | None, str | None]:
    """(leírás a szerzősor nélkül, szerzőnév) — a szerzősor a leírás utolsó sora."""
    if not description:
        return None, None
    lines = description.rstrip().split("\n")
    if lines and lines[-1].startswith(AUTHOR_MARKER):
        author = lines[-1][len(AUTHOR_MARKER):].strip() or None
        rest = "\n".join(lines[:-1]).rstrip()
        return (rest or None), author
    return description, None


def with_author_marker(description: str | None, author: str | None) -> str | None:
    base, _old = split_author_marker(description)
    if not author:
        return base
    line = AUTHOR_MARKER + author
    return f"{base}\n\n{line}" if base else line
