"""Admin digitális mesekönyvek — írás: owner; lista: maintenance + owner."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db, is_relation_missing_error, is_undefined_column_error
from db_models import DigitalStorybook, DigitalStorybookPage
from dependencies import CurrentAdmin, require_role
from image_upload import (
    UPLOADS_ROOT,
    delete_uploaded_file_by_url,
    public_url_for,
    save_uploaded_image,
    uploads_dir_for,
)
from models import (
    AdminImageUploadResponse,
    AdminStorybookMediaUploadResponse,
    StorybookAdminListItem,
    StorybookAdminPageRead,
    StorybookAdminRead,
    StorybookCreate,
    StorybookPageCreate,
    StorybookPageUpdate,
    StorybookPagesReorder,
    StorybookUpdate,
)
from services import find_digital_storybook, find_storybook_page_for_book
from storybook_slug import allocate_unique_storybook_slug

router = APIRouter(prefix="/storybooks", tags=["admin-storybooks"])

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_MAX_AUDIO_BYTES = 25 * 1024 * 1024
_ALLOWED_AUDIO_EXT = {".mp3", ".m4a", ".ogg", ".wav", ".webm"}
_MAX_PAGES_PER_BOOK = 80

logger = logging.getLogger(__name__)

_ALLOWED_AUDIO_CT_PREFIX = ("audio/",)


def _audio_magic_matches(body: bytes, suffix: str) -> bool:
    if len(body) < 12:
        return False
    if suffix == ".ogg" and body[:4] == b"OggS":
        return True
    if suffix == ".wav" and body[:4] == b"RIFF" and body[8:12] == b"WAVE":
        return True
    if suffix == ".webm" and len(body) >= 4 and body[:4] == b"\x1a\x45\xdf\xa3":
        return True
    if suffix in (".mp3",) and (body[:3] == b"ID3" or ((body[0] & 0xFF) == 0xFF and (body[1] & 0xE0) == 0xE0)):
        return True
    if suffix == ".m4a" and body[4:8] == b"ftyp":
        return True
    return False


def _content_type_ok_audio(ct: str | None) -> bool:
    if not ct:
        return True
    c = ct.split(";")[0].strip().lower()
    if c == "application/octet-stream":
        return True
    return c.startswith(_ALLOWED_AUDIO_CT_PREFIX)


def _safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem_safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-")
    return (stem_safe or "file")[:72]


def _assert_under_uploads(dest: Path) -> None:
    dest.resolve().relative_to(UPLOADS_ROOT.resolve())


def _storybook_media_subdir(book_id: int) -> str:
    return f"storybooks/{int(book_id)}"


def _load_pages(db: Session, book_id: int) -> list[DigitalStorybookPage]:
    try:
        return list(
            db.scalars(
                select(DigitalStorybookPage)
                .where(DigitalStorybookPage.book_id == book_id)
                .order_by(DigitalStorybookPage.page_index.asc(), DigitalStorybookPage.id.asc())
            ).all()
        )
    except SQLAlchemyError as e:
        db.rollback()
        if is_undefined_column_error(e):
            raise HTTPException(
                status_code=503,
                detail=(
                    "A mesekönyv oldalak táblája elavult (hiányzó oszlopok). "
                    "Futtasd a szerveren: alembic upgrade head"
                ),
            ) from e
        raise


def _reindex_pages(db: Session, book_id: int) -> None:
    pages = _load_pages(db, book_id)
    for i, p in enumerate(pages, start=1):
        p.page_index = i


def _require_storybook_tables(db: Session) -> None:
    """503 ha a mesekönyv táblák nincsenek (pl. nem futott az Alembic 013+)."""
    try:
        db.execute(text("SELECT 1 FROM digital_storybooks LIMIT 1"))
    except SQLAlchemyError as e:
        db.rollback()
        if is_relation_missing_error(e):
            logger.error(
                "Storybook query failed: missing digital_storybooks (run: alembic upgrade head). %s",
                e,
            )
            raise HTTPException(
                status_code=503,
                detail="A mesekönyv adatbázis táblák hiányoznak. Futtasd a szerveren: alembic upgrade head",
            ) from e
        logger.exception("Storybook query failed: %s", e)
        raise


def _to_admin_read(book: DigitalStorybook, pages: list[DigitalStorybookPage]) -> StorybookAdminRead:
    pr = [StorybookAdminPageRead.model_validate(p) for p in pages]
    anim = book.animation_settings if isinstance(book.animation_settings, dict) else {}
    return StorybookAdminRead(
        id=book.id,
        title=book.title,
        slug=book.slug,
        description=book.description,
        cover_image_url=book.cover_image_url,
        is_published=book.is_published,
        animation_settings=anim,
        created_at=book.created_at,
        updated_at=book.updated_at,
        pages=pr,
    )


@router.get("", response_model=list[StorybookAdminListItem])
def admin_list_storybooks(
    visibility: Literal["all", "draft", "published"] = Query("all", description="draft = nem közzétett"),
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    logger.info("Loading admin storybooks… (visibility=%s)", visibility)
    logger.info("Admin user validated")
    stmt = select(DigitalStorybook).order_by(DigitalStorybook.updated_at.desc(), DigitalStorybook.id.desc())
    if visibility == "draft":
        stmt = stmt.where(DigitalStorybook.is_published.is_(False))
    elif visibility == "published":
        stmt = stmt.where(DigitalStorybook.is_published.is_(True))
    try:
        logger.info("Querying storybooks table")
        rows = db.scalars(stmt).all()
        out = [StorybookAdminListItem.model_validate(r) for r in rows]
        logger.info("Storybook query success (count=%s)", len(out))
        return out
    except SQLAlchemyError as e:
        db.rollback()
        if is_relation_missing_error(e):
            logger.error(
                "Storybook query failed: %s — missing tables; run: alembic upgrade head",
                e,
            )
            return []
        logger.exception("Storybook query failed: %s", e)
        raise
    except Exception:
        raise


@router.get("/{book_id}", response_model=StorybookAdminRead)
def admin_get_storybook(
    book_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    _require_storybook_tables(db)
    book = find_digital_storybook(db, book_id)
    pages = _load_pages(db, book.id)
    return _to_admin_read(book, pages)


@router.post("", response_model=StorybookAdminRead, status_code=status.HTTP_201_CREATED)
def admin_create_storybook(
    payload: StorybookCreate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    _require_storybook_tables(db)
    slug = allocate_unique_storybook_slug(db, payload.title)
    desc = payload.description.strip() if payload.description else None
    row = DigitalStorybook(
        title=payload.title.strip(),
        slug=slug,
        description=desc,
        cover_image_url=None,
        is_published=False,
        animation_settings={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_admin_read(row, [])


@router.patch("/{book_id}", response_model=StorybookAdminRead)
def admin_update_storybook(
    book_id: int,
    payload: StorybookUpdate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    _require_storybook_tables(db)
    book = find_digital_storybook(db, book_id)
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        book.title = str(data["title"]).strip()
    if "description" in data:
        if data["description"] is None:
            book.description = None
        else:
            book.description = str(data["description"]).strip() or None
    if "cover_image_url" in data:
        v = data["cover_image_url"]
        book.cover_image_url = v.strip() if isinstance(v, str) and v.strip() else None
    if "is_published" in data and data["is_published"] is not None:
        book.is_published = bool(data["is_published"])
    if "animation_settings" in data and data["animation_settings"] is not None:
        book.animation_settings = data["animation_settings"]
    db.commit()
    db.refresh(book)
    pages = _load_pages(db, book.id)
    return _to_admin_read(book, pages)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_storybook(
    book_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    _require_storybook_tables(db)
    book = find_digital_storybook(db, book_id)
    db.delete(book)
    db.commit()
    return None


@router.post("/{book_id}/pages", response_model=StorybookAdminRead, status_code=status.HTTP_201_CREATED)
def admin_add_storybook_page(
    book_id: int,
    payload: StorybookPageCreate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    _require_storybook_tables(db)
    book = find_digital_storybook(db, book_id)
    n = int(db.scalar(select(func.count()).select_from(DigitalStorybookPage).where(DigitalStorybookPage.book_id == book_id)) or 0)
    if n >= _MAX_PAGES_PER_BOOK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Legfeljebb {_MAX_PAGES_PER_BOOK} oldal engedélyezett könyvenként.",
        )
    max_idx = db.scalar(select(func.max(DigitalStorybookPage.page_index)).where(DigitalStorybookPage.book_id == book_id))
    next_idx = int(max_idx or 0) + 1
    page = DigitalStorybookPage(
        book_id=book.id,
        page_index=next_idx,
        title=payload.title.strip() if payload.title else None,
        body_text=(payload.body_text or "").strip(),
        image_url=None,
        audio_url=None,
        text_position_vertical="center",
        text_position_horizontal="center",
        text_box_style="card",
        extra={},
    )
    db.add(page)
    db.commit()
    db.refresh(book)
    pages = _load_pages(db, book.id)
    return _to_admin_read(book, pages)


@router.patch("/{book_id}/pages/{page_id}", response_model=StorybookAdminRead)
def admin_update_storybook_page(
    book_id: int,
    page_id: int,
    payload: StorybookPageUpdate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    _require_storybook_tables(db)
    find_digital_storybook(db, book_id)
    page = find_storybook_page_for_book(db, book_id, page_id)
    data = payload.model_dump(exclude_unset=True)
    if "title" in data:
        t = data["title"]
        page.title = t.strip() if isinstance(t, str) and t.strip() else None
    if "body_text" in data and data["body_text"] is not None:
        page.body_text = str(data["body_text"]).strip()
    if "audio_url" in data:
        v = data["audio_url"]
        page.audio_url = v.strip() if isinstance(v, str) and v.strip() else None
    if "extra" in data and data["extra"] is not None:
        page.extra = data["extra"]
    if "text_position_vertical" in data and data["text_position_vertical"] is not None:
        page.text_position_vertical = data["text_position_vertical"]
    if "text_position_horizontal" in data and data["text_position_horizontal"] is not None:
        page.text_position_horizontal = data["text_position_horizontal"]
    if "text_box_style" in data and data["text_box_style"] is not None:
        page.text_box_style = data["text_box_style"]
    if "text_x_percent" in data:
        page.text_x_percent = data["text_x_percent"]
    if "text_y_percent" in data:
        page.text_y_percent = data["text_y_percent"]
    db.commit()
    book = find_digital_storybook(db, book_id)
    pages = _load_pages(db, book.id)
    return _to_admin_read(book, pages)


@router.delete("/{book_id}/pages/{page_id}", response_model=StorybookAdminRead)
def admin_delete_storybook_page(
    book_id: int,
    page_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    _require_storybook_tables(db)
    find_digital_storybook(db, book_id)
    page = find_storybook_page_for_book(db, book_id, page_id)
    db.delete(page)
    db.flush()
    _reindex_pages(db, book_id)
    db.commit()
    book = find_digital_storybook(db, book_id)
    pages = _load_pages(db, book.id)
    return _to_admin_read(book, pages)


@router.post("/{book_id}/pages/reorder", response_model=StorybookAdminRead)
def admin_reorder_storybook_pages(
    book_id: int,
    payload: StorybookPagesReorder,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    _require_storybook_tables(db)
    find_digital_storybook(db, book_id)
    existing = _load_pages(db, book_id)
    ids_db = {p.id for p in existing}
    ordered = payload.ordered_page_ids
    if set(ordered) != ids_db or len(ordered) != len(ids_db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A sorrendhez minden oldal azonosítóját pontosan egyszer add meg.",
        )
    index_map = {pid: i for i, pid in enumerate(ordered, start=1)}
    for p in existing:
        p.page_index = index_map[p.id]
    db.commit()
    book = find_digital_storybook(db, book_id)
    pages = _load_pages(db, book.id)
    return _to_admin_read(book, pages)


@router.post("/{book_id}/cover", response_model=AdminImageUploadResponse)
async def admin_upload_storybook_cover(
    book_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    _require_storybook_tables(db)
    book = find_digital_storybook(db, book_id)
    prev = book.cover_image_url
    sub = _storybook_media_subdir(book_id)
    url, filename = await save_uploaded_image(file, subdir=sub, filename_prefix="cover")
    book.cover_image_url = url
    db.commit()
    if prev and str(prev).strip() and str(prev).strip() != url.strip():
        delete_uploaded_file_by_url(prev)
    return AdminImageUploadResponse(url=url, filename=filename)


@router.post("/{book_id}/pages/{page_id}/image", response_model=AdminImageUploadResponse)
async def admin_upload_storybook_page_image(
    book_id: int,
    page_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    _require_storybook_tables(db)
    find_digital_storybook(db, book_id)
    page = find_storybook_page_for_book(db, book_id, page_id)
    prev = page.image_url
    sub = _storybook_media_subdir(book_id)
    url, filename = await save_uploaded_image(file, subdir=sub, filename_prefix=f"page-{page_id}")
    page.image_url = url
    db.commit()
    if prev and str(prev).strip() and str(prev).strip() != url.strip():
        delete_uploaded_file_by_url(prev)
    return AdminImageUploadResponse(url=url, filename=filename)


@router.post("/{book_id}/pages/{page_id}/audio", response_model=AdminStorybookMediaUploadResponse)
async def admin_upload_storybook_page_audio(
    book_id: int,
    page_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    _require_storybook_tables(db)
    find_digital_storybook(db, book_id)
    page = find_storybook_page_for_book(db, book_id, page_id)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nincs kiválasztott fájl.")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_AUDIO_EXT:
        raise HTTPException(
            status_code=415,
            detail="Csak hangfájl engedélyezett (mp3, m4a, ogg, wav, webm).",
        )
    body = await file.read()
    if not body:
        raise HTTPException(status_code=400, detail="Üres fájl.")
    if len(body) > _MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="A hangfájl túl nagy — legfeljebb 25 MB engedélyezett.")
    if not _content_type_ok_audio(file.content_type):
        raise HTTPException(
            status_code=415,
            detail="A feltöltött fájl MIME típusa nem tűnik hangfájlnak.",
        )
    if not _audio_magic_matches(body, suffix):
        raise HTTPException(
            status_code=415,
            detail="A fájl tartalma nem egyezik az engedélyezett hangformátumokkal — ellenőrizd a kiterjesztést és a fájlt.",
        )
    sub = _storybook_media_subdir(book_id)
    dest_dir = uploads_dir_for(sub)
    final_name = f"audio-page-{page_id}-{_safe_stem(file.filename)}-{uuid.uuid4().hex[:10]}{suffix}"
    dest = (dest_dir / final_name).resolve()
    _assert_under_uploads(dest)
    prev = page.audio_url
    dest.write_bytes(body)
    rel = public_url_for(sub, final_name)
    page.audio_url = rel
    db.commit()
    if prev and str(prev).strip() and str(prev).strip() != rel.strip():
        delete_uploaded_file_by_url(prev)
    return AdminStorybookMediaUploadResponse(url=rel, filename=final_name)
