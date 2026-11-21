"""Nyitási akció — felhasználói mesekönyv-piszkozatok (``/my/storybooks``) és admin beküldési lista.

Szabályok (mindegyikhez teszt a ``tests/test_storybooks_user.py`` fájlban):
  * a felhasználói API sosem fogad és sosem állít ``is_published`` értéket; csak az admin publikál;
  * minden lekérdezés a tulajdonosra szűr, idegen könyv = 404;
  * beküldés után a felhasználó nem szerkeszt (visszavonhatja), publikálás után sem;
  * hang, ``extra`` és ``audio_url`` felhasználónak nem engedett;
  * a funkció az env kapcsolóval (``USER_STORYBOOKS_ENABLED``) leállítható.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth_limits import limiter
from database import get_db
from db_models import AppUser, DigitalStorybook, DigitalStorybookPage
from dependencies import CurrentAdmin, require_email_verified_shop_user, require_role
from models import (
    AdminImageUploadResponse,
    StorybookAdminRead,
    StorybookPageCreate,
    StorybookPageUpdate,
    StorybookPagesReorder,
)
from routers import storybooks_admin as adm
from services import find_digital_storybook
from storybook_slug import allocate_unique_storybook_slug
from storybook_submissions import (
    CONSENT_VERSION,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    UserStorybookSubmission,
    ensure_submissions_table,
    max_open_books,
    max_pages_per_book,
    split_author_marker,
    user_storybooks_enabled,
    with_author_marker,
)

router = APIRouter(prefix="/my/storybooks", tags=["my-storybooks"])
admin_router = APIRouter(prefix="/storybook-submissions", tags=["admin-storybook-submissions"])

_USER_MAX_IMAGE_BYTES = 3 * 1024 * 1024
_USER_MAX_PAGE_TEXT = 6000
_USER_MAX_LAYOUT_BYTES = 60_000

_NOT_FOUND = "Nincs ilyen mesekönyv."


# ---------------------------------------------------------------- sémák


class UserStorybookCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=600)


class UserStorybookUpdate(BaseModel):
    """Szándékosan nincs benne is_published / animation_settings; ismeretlen mező = 422."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=600)


class UserStorybookSubmit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    author_name: str = Field(..., min_length=2, max_length=60)
    consent: bool

    @field_validator("author_name")
    @classmethod
    def _single_line(cls, v: str) -> str:
        if "\n" in v or "\r" in v:
            raise ValueError("A szerzői név egy sor lehet.")
        return v


class UserStorybookRead(StorybookAdminRead):
    submission_status: str
    can_edit: bool
    author_name: str | None = None
    admin_note: str | None = None
    submitted_at: datetime | None = None


class UserStorybookListItem(BaseModel):
    id: int
    slug: str
    title: str
    cover_image_url: str | None
    is_published: bool
    updated_at: datetime
    submission_status: str
    can_edit: bool
    author_name: str | None = None
    admin_note: str | None = None


class UserStorybooksStatus(BaseModel):
    enabled: bool
    max_books: int = 0
    max_pages: int = 0
    max_image_mb: int = 0
    consent_version: str = ""


class SubmissionAdminItem(BaseModel):
    book_id: int
    title: str
    slug: str
    status: str
    is_published: bool
    author_name: str | None
    owner_user_id: int
    owner_label: str
    owner_email: str
    submitted_at: datetime | None
    updated_at: datetime
    admin_note: str | None


class SubmissionPendingCount(BaseModel):
    pending: int


class SubmissionReturn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    note: str | None = Field(None, max_length=1000)


# ---------------------------------------------------------------- kapuk


def require_feature() -> None:
    """Kapcsoló: kikapcsolva a /my/storybooks útvonalak nem léteznek (404)."""
    if not user_storybooks_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nem található.")


def _gate(
    _enabled: None = Depends(require_feature),
    user: AppUser = Depends(require_email_verified_shop_user),
) -> AppUser:
    ensure_submissions_table()
    return user


def _is_editable(sub: UserStorybookSubmission, book: DigitalStorybook) -> bool:
    return sub.status == STATUS_DRAFT and not book.is_published


def _effective_status(sub: UserStorybookSubmission, book: DigitalStorybook) -> str:
    return "published" if book.is_published else sub.status


def _owned(db: Session, user: AppUser, book_id: int) -> tuple[UserStorybookSubmission, DigitalStorybook]:
    sub = db.scalar(
        select(UserStorybookSubmission).where(
            UserStorybookSubmission.book_id == book_id,
            UserStorybookSubmission.owner_user_id == user.id,
        )
    )
    if sub is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    book = find_digital_storybook(db, book_id)
    return sub, book


def _owned_editable(db: Session, user: AppUser, book_id: int) -> tuple[UserStorybookSubmission, DigitalStorybook]:
    sub, book = _owned(db, user, book_id)
    if not _is_editable(sub, book):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A beküldött mesét nem lehet szerkeszteni. Vond vissza a beküldést, ha módosítanál rajta.",
        )
    return sub, book


def _read(db: Session, sub: UserStorybookSubmission, book: DigitalStorybook) -> UserStorybookRead:
    db.refresh(book)
    db.refresh(sub)
    base = adm._to_admin_read(book, adm._load_pages(db, book.id))
    data = base.model_dump()
    desc, _author = split_author_marker(data.get("description"))
    data["description"] = desc
    return UserStorybookRead(
        **data,
        submission_status=_effective_status(sub, book),
        can_edit=_is_editable(sub, book),
        author_name=sub.author_name,
        admin_note=sub.admin_note,
        submitted_at=sub.submitted_at,
    )


def _page_count(db: Session, book_id: int) -> int:
    return int(db.scalar(select(func.count()).select_from(DigitalStorybookPage).where(DigitalStorybookPage.book_id == book_id)) or 0)


def _open_book_count(db: Session, user: AppUser) -> int:
    """Még nem publikált könyvek száma (piszkozat + beküldött)."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(UserStorybookSubmission)
            .join(DigitalStorybook, DigitalStorybook.id == UserStorybookSubmission.book_id)
            .where(
                UserStorybookSubmission.owner_user_id == user.id,
                DigitalStorybook.is_published.is_(False),
            )
        )
        or 0
    )


def _check_image_size(file: UploadFile) -> None:
    size = getattr(file, "size", None)
    if size is not None and size > _USER_MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="A kép túl nagy — legfeljebb 3 MB engedélyezett.")


# ---------------------------------------------------------------- felhasználói végpontok


@router.get("/status", response_model=UserStorybooksStatus)
def promo_status() -> UserStorybooksStatus:
    """Nyilvános (bejelentkezés nélküli) állapot — a frontend ebből tudja, kell-e a belépési pont."""
    if not user_storybooks_enabled():
        return UserStorybooksStatus(enabled=False)
    return UserStorybooksStatus(
        enabled=True,
        max_books=max_open_books(),
        max_pages=max_pages_per_book(),
        max_image_mb=_USER_MAX_IMAGE_BYTES // (1024 * 1024),
        consent_version=CONSENT_VERSION,
    )


@router.get("", response_model=list[UserStorybookListItem])
def my_list(db: Session = Depends(get_db), user: AppUser = Depends(_gate)):
    rows = db.execute(
        select(UserStorybookSubmission, DigitalStorybook)
        .join(DigitalStorybook, DigitalStorybook.id == UserStorybookSubmission.book_id)
        .where(UserStorybookSubmission.owner_user_id == user.id)
        .order_by(DigitalStorybook.updated_at.desc(), DigitalStorybook.id.desc())
    ).all()
    out: list[UserStorybookListItem] = []
    for sub, book in rows:
        out.append(
            UserStorybookListItem(
                id=book.id,
                slug=book.slug,
                title=book.title,
                cover_image_url=book.cover_image_url,
                is_published=bool(book.is_published),
                updated_at=book.updated_at,
                submission_status=_effective_status(sub, book),
                can_edit=_is_editable(sub, book),
                author_name=sub.author_name,
                admin_note=sub.admin_note,
            )
        )
    return out


@router.post("", response_model=UserStorybookRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
def my_create(
    request: Request,
    payload: UserStorybookCreate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(_gate),
):
    if _open_book_count(db, user) >= max_open_books():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Egyszerre legfeljebb {max_open_books()} be nem fejezett (nem publikált) meséd lehet.",
        )
    book = DigitalStorybook(
        title=payload.title,
        slug=allocate_unique_storybook_slug(db, payload.title),
        description=payload.description or None,
        cover_image_url=None,
        is_published=False,  # kényszerítve: a felhasználó sosem publikál
        animation_settings={},
    )
    db.add(book)
    db.flush()
    sub = UserStorybookSubmission(book_id=book.id, owner_user_id=user.id, status=STATUS_DRAFT)
    db.add(sub)
    db.commit()
    return _read(db, sub, book)


@router.get("/{book_id}", response_model=UserStorybookRead)
def my_get(book_id: int, db: Session = Depends(get_db), user: AppUser = Depends(_gate)):
    sub, book = _owned(db, user, book_id)
    return _read(db, sub, book)


@router.patch("/{book_id}", response_model=UserStorybookRead)
def my_update(
    book_id: int,
    payload: UserStorybookUpdate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(_gate),
):
    sub, book = _owned_editable(db, user, book_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("title"):
        book.title = data["title"]
    if "description" in data:
        book.description = (data["description"] or "").strip() or None
    db.commit()
    return _read(db, sub, book)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def my_delete(book_id: int, db: Session = Depends(get_db), user: AppUser = Depends(_gate)):
    sub, book = _owned_editable(db, user, book_id)
    adm.admin_delete_storybook(book.id, db=db, _admin=None)
    return None


@router.post("/{book_id}/pages", response_model=UserStorybookRead, status_code=status.HTTP_201_CREATED)
def my_add_page(
    book_id: int,
    payload: StorybookPageCreate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(_gate),
):
    sub, book = _owned_editable(db, user, book_id)
    if _page_count(db, book.id) >= max_pages_per_book():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Egy mese legfeljebb {max_pages_per_book()} oldalas lehet.",
        )
    if len(payload.body_text or "") > _USER_MAX_PAGE_TEXT:
        raise HTTPException(status_code=422, detail="Az oldal szövege túl hosszú.")
    adm.admin_add_storybook_page(book.id, payload, db=db, _admin=None)
    return _read(db, sub, book)


@router.patch("/{book_id}/pages/{page_id}", response_model=UserStorybookRead)
def my_update_page(
    book_id: int,
    page_id: int,
    payload: StorybookPageUpdate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(_gate),
):
    sub, book = _owned_editable(db, user, book_id)
    # Hang és szabad "extra" mező felhasználónak nem engedett: csendben eldobjuk.
    payload.__pydantic_fields_set__.discard("audio_url")
    payload.__pydantic_fields_set__.discard("extra")
    if payload.body_text is not None and len(payload.body_text) > _USER_MAX_PAGE_TEXT:
        raise HTTPException(status_code=422, detail="Az oldal szövege túl hosszú.")
    if payload.layout_json is not None and len(json.dumps(payload.layout_json)) > _USER_MAX_LAYOUT_BYTES:
        raise HTTPException(status_code=422, detail="Az oldal elrendezése túl nagy.")
    adm.admin_update_storybook_page(book.id, page_id, payload, db=db, _admin=None)
    return _read(db, sub, book)


@router.delete("/{book_id}/pages/{page_id}", response_model=UserStorybookRead)
def my_delete_page(
    book_id: int,
    page_id: int,
    db: Session = Depends(get_db),
    user: AppUser = Depends(_gate),
):
    sub, book = _owned_editable(db, user, book_id)
    adm.admin_delete_storybook_page(book.id, page_id, db=db, _admin=None)
    return _read(db, sub, book)


@router.post("/{book_id}/pages/reorder", response_model=UserStorybookRead)
def my_reorder_pages(
    book_id: int,
    payload: StorybookPagesReorder,
    db: Session = Depends(get_db),
    user: AppUser = Depends(_gate),
):
    sub, book = _owned_editable(db, user, book_id)
    adm.admin_reorder_storybook_pages(book.id, payload, db=db, _admin=None)
    return _read(db, sub, book)


@router.post("/{book_id}/cover", response_model=AdminImageUploadResponse)
@limiter.limit("60/hour")
async def my_upload_cover(
    request: Request,
    book_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AppUser = Depends(_gate),
):
    _owned_editable(db, user, book_id)
    _check_image_size(file)
    return await adm.admin_upload_storybook_cover(book_id, file=file, db=db, _admin=None)


@router.delete("/{book_id}/cover", response_model=UserStorybookRead)
def my_remove_cover(book_id: int, db: Session = Depends(get_db), user: AppUser = Depends(_gate)):
    sub, book = _owned_editable(db, user, book_id)
    adm.admin_remove_storybook_cover(book.id, db=db, _admin=None)
    return _read(db, sub, book)


@router.post("/{book_id}/pages/{page_id}/image", response_model=AdminImageUploadResponse)
@limiter.limit("60/hour")
async def my_upload_page_image(
    request: Request,
    book_id: int,
    page_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AppUser = Depends(_gate),
):
    _owned_editable(db, user, book_id)
    _check_image_size(file)
    return await adm.admin_upload_storybook_page_image(book_id, page_id, file=file, db=db, _admin=None)


@router.delete("/{book_id}/pages/{page_id}/image", response_model=UserStorybookRead)
def my_remove_page_image(
    book_id: int,
    page_id: int,
    db: Session = Depends(get_db),
    user: AppUser = Depends(_gate),
):
    sub, book = _owned_editable(db, user, book_id)
    adm.admin_remove_storybook_page_image(book.id, page_id, db=db, _admin=None)
    return _read(db, sub, book)


@router.post("/{book_id}/submit", response_model=UserStorybookRead)
@limiter.limit("20/hour")
def my_submit(
    request: Request,
    book_id: int,
    payload: UserStorybookSubmit,
    db: Session = Depends(get_db),
    user: AppUser = Depends(_gate),
):
    sub, book = _owned_editable(db, user, book_id)
    if not payload.consent:
        raise HTTPException(status_code=422, detail="A beküldéshez el kell fogadnod a feltételeket.")
    if _page_count(db, book.id) < 1:
        raise HTTPException(status_code=422, detail="Üres mesét nem lehet beküldeni — adj hozzá legalább egy oldalt.")
    now = datetime.now(UTC)
    sub.status = STATUS_SUBMITTED
    sub.author_name = payload.author_name
    sub.submitted_at = now
    sub.consent_at = now
    sub.consent_version = CONSENT_VERSION
    sub.admin_note = None
    book.description = with_author_marker(book.description, payload.author_name)
    db.commit()
    return _read(db, sub, book)


@router.post("/{book_id}/withdraw", response_model=UserStorybookRead)
def my_withdraw(book_id: int, db: Session = Depends(get_db), user: AppUser = Depends(_gate)):
    sub, book = _owned(db, user, book_id)
    if book.is_published:
        raise HTTPException(status_code=409, detail="A már publikált mesét nem lehet visszavonni.")
    if sub.status != STATUS_SUBMITTED:
        raise HTTPException(status_code=409, detail="Ez a mese nincs beküldve.")
    sub.status = STATUS_DRAFT
    book.description = with_author_marker(book.description, None)
    db.commit()
    return _read(db, sub, book)


# ---------------------------------------------------------------- admin: beküldött mesék


def _pending_filter():
    return (UserStorybookSubmission.status == STATUS_SUBMITTED) & (DigitalStorybook.is_published.is_(False))


@admin_router.get("/pending-count", response_model=SubmissionPendingCount)
def admin_pending_count(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    ensure_submissions_table()
    n = db.scalar(
        select(func.count())
        .select_from(UserStorybookSubmission)
        .join(DigitalStorybook, DigitalStorybook.id == UserStorybookSubmission.book_id)
        .where(_pending_filter())
    )
    return SubmissionPendingCount(pending=int(n or 0))


@admin_router.get("", response_model=list[SubmissionAdminItem])
def admin_list_submissions(
    state: Literal["pending", "draft", "published", "all"] = Query("pending"),
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    ensure_submissions_table()
    stmt = (
        select(UserStorybookSubmission, DigitalStorybook, AppUser)
        .join(DigitalStorybook, DigitalStorybook.id == UserStorybookSubmission.book_id)
        .join(AppUser, AppUser.id == UserStorybookSubmission.owner_user_id)
    )
    if state == "pending":
        stmt = stmt.where(_pending_filter())
    elif state == "draft":
        stmt = stmt.where(UserStorybookSubmission.status == STATUS_DRAFT, DigitalStorybook.is_published.is_(False))
    elif state == "published":
        stmt = stmt.where(DigitalStorybook.is_published.is_(True))
    stmt = stmt.order_by(
        UserStorybookSubmission.submitted_at.desc().nulls_last(), DigitalStorybook.updated_at.desc()
    )
    out: list[SubmissionAdminItem] = []
    for sub, book, owner in db.execute(stmt).all():
        out.append(
            SubmissionAdminItem(
                book_id=book.id,
                title=book.title,
                slug=book.slug,
                status=_effective_status(sub, book),
                is_published=bool(book.is_published),
                author_name=sub.author_name,
                owner_user_id=owner.id,
                owner_label=(owner.nickname or owner.username or "").strip(),
                owner_email=owner.email,
                submitted_at=sub.submitted_at,
                updated_at=book.updated_at,
                admin_note=sub.admin_note,
            )
        )
    return out


@admin_router.post("/{book_id}/return", response_model=SubmissionPendingCount)
def admin_return_to_author(
    book_id: int,
    payload: SubmissionReturn,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    """Visszaküldés a szerzőnek javításra (megjegyzéssel); a mese újra szerkeszthető lesz."""
    ensure_submissions_table()
    sub = db.scalar(select(UserStorybookSubmission).where(UserStorybookSubmission.book_id == book_id))
    if sub is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    book = find_digital_storybook(db, book_id)
    if book.is_published:
        raise HTTPException(status_code=409, detail="A publikált mesét előbb vedd vissza piszkozatba.")
    sub.status = STATUS_DRAFT
    sub.admin_note = (payload.note or "").strip() or None
    book.description = with_author_marker(book.description, None)
    db.commit()
    return admin_pending_count(db=db, _admin=_admin)
