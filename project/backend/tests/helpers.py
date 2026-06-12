"""Közös pytest segédek — seed, auth fejlécek, minimális képfájl bájtok."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

from auth import create_admin_token
from database import SessionLocal
from db_models import AppUser, GalleryItem, NewsPost
from frontend_assets import page_background_asset_path
from image_upload import public_url_for, uploads_dir_for
from password_utils import hash_password
from user_tokens import issue_user_access_token

# 1×1 átlátszó PNG
MINIMAL_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVRQIW2P8z8DwHwBFwAJAOnF2G7pAAAAAElFTkSuQmCC"
)


def auth_headers(user_id: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        row = db.get(AppUser, user_id)
        tv = int(row.token_version or 0) if row is not None else 0
    finally:
        db.close()
    return {"Authorization": "Bearer " + issue_user_access_token(user_id, token_version=tv)}


def admin_headers(*, role: str = "owner") -> dict[str, str]:
    return {"Authorization": "Bearer " + create_admin_token(username="pytest-admin", role=role)}


def seed_unverified_user(
    *,
    email: str = "unverified@example.com",
    password: str = "test-password-123",
    username: str = "unverifieduser",
) -> int:
    db = SessionLocal()
    try:
        u = AppUser(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_active=True,
            is_banned=False,
            is_deleted=False,
            email_verified_at=None,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return int(u.id)
    finally:
        db.close()


def seed_verified_user(
    *,
    email: str = "pytestbuyer@example.com",
    password: str = "test-password-123",
    username: str = "pytestbuyer",
) -> int:
    db = SessionLocal()
    try:
        u = AppUser(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_active=True,
            is_banned=False,
            is_deleted=False,
            email_verified_at=datetime.now(UTC),
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return int(u.id)
    finally:
        db.close()


def seed_published_news(*, title: str = "Teszt hír", slug: str = "teszt-hir") -> int:
    db = SessionLocal()
    try:
        row = NewsPost(
            title=title,
            slug=slug,
            summary="Összefoglaló",
            body="Törzs",
            is_published=True,
            is_featured=True,
            published_at=datetime.now(UTC),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)
    finally:
        db.close()


def _gallery_seed_image_bytes() -> bytes:
    bg = page_background_asset_path()
    if bg.is_file() and bg.stat().st_size >= 120:
        return bg.read_bytes()
    return MINIMAL_PNG_BYTES


def seed_gallery_items(count: int) -> list[int]:
    gallery_dir = uploads_dir_for("gallery")
    blob = _gallery_seed_image_bytes()
    db = SessionLocal()
    try:
        ids: list[int] = []
        for i in range(count):
            fn = f"test-{i + 1}.png"
            (gallery_dir / fn).write_bytes(blob)
            row = GalleryItem(
                title=f"Kép {i + 1}",
                image_url=public_url_for("gallery", fn),
                description=None,
                sort_order=i,
            )
            db.add(row)
            db.flush()
            ids.append(int(row.id))
        db.commit()
        return ids
    finally:
        db.close()
