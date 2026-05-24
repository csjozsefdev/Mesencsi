"""Közös helyi képfeltöltés: ``media/uploads/…`` + URL prefix ``/media/uploads/…``."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

_BACKEND_DIR = Path(__file__).resolve().parent
UPLOADS_ROOT = (_BACKEND_DIR / "media" / "uploads").resolve()
FRONTEND_ROOT = (_BACKEND_DIR.parent / "frontend").resolve()
PUBLIC_UPLOAD_PREFIX = "/media/uploads"

_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_ALLOWED_IMAGE_CT = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def image_magic_matches(body: bytes) -> bool:
    if len(body) < 12:
        return False
    if body[:3] == b"\xff\xd8\xff":
        return True
    if body[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if body[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return True
    return False


def content_type_ok_image(ct: str | None) -> bool:
    if not ct:
        return True
    c = ct.split(";")[0].strip().lower()
    return c in _ALLOWED_IMAGE_CT or c == "application/octet-stream"


def safe_stem(name: str, default: str = "file") -> str:
    stem = Path(name).stem
    stem_safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-")
    return (stem_safe or default)[:72]


def assert_relative_subdir(subdir: str) -> str:
    """Csak egy szintű vagy storybooks/<id> formátum — path traversal ellen."""
    s = (subdir or "").strip().replace("\\", "/").strip("/")
    if not s or ".." in s or s.startswith("/"):
        raise ValueError("Érvénytelen alkönyvtár.")
    parts = [p for p in s.split("/") if p]
    if not parts:
        raise ValueError("Érvénytelen alkönyvtár.")
    if len(parts) == 1:
        if not re.fullmatch(r"[a-z0-9_-]+", parts[0]):
            raise ValueError("Érvénytelen alkönyvtár.")
        return parts[0]
    if len(parts) == 2 and parts[0] == "storybooks" and re.fullmatch(r"[0-9]+", parts[1]):
        return f"storybooks/{parts[1]}"
    raise ValueError("Érvénytelen alkönyvtár.")


def uploads_dir_for(subdir: str) -> Path:
    rel = assert_relative_subdir(subdir)
    d = (UPLOADS_ROOT / rel).resolve()
    d.mkdir(parents=True, exist_ok=True)
    try:
        d.relative_to(UPLOADS_ROOT)
    except ValueError as e:
        raise ValueError("Érvénytelen cél útvonal.") from e
    return d


def public_url_for(subdir: str, filename: str) -> str:
    rel = assert_relative_subdir(subdir)
    fn = Path(filename).name
    if not fn or fn != filename:
        raise ValueError("Érvénytelen fájlnév.")
    return f"{PUBLIC_UPLOAD_PREFIX}/{rel}/{fn}"


def delete_uploaded_file_by_url(url: str | None) -> None:
    """Törli a fájlt, ha a tárolt érték a saját uploads prefix alá mutat (biztonságos)."""
    if not url or not isinstance(url, str):
        return
    u = url.strip()
    if not u.startswith(PUBLIC_UPLOAD_PREFIX + "/"):
        return
    rel = u[len(PUBLIC_UPLOAD_PREFIX) :].lstrip("/")
    if ".." in rel or rel.startswith("/"):
        return
    path = (UPLOADS_ROOT / rel).resolve()
    try:
        path.relative_to(UPLOADS_ROOT)
    except ValueError:
        return
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


async def save_uploaded_image(
    file: UploadFile,
    *,
    subdir: str,
    filename_prefix: str,
) -> tuple[str, str]:
    """
    Validálja és elmenti a képet.

    Returns:
        (public_url, filename) — pl. ``("/media/uploads/gallery/x.jpg", "x.jpg")``
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nincs kiválasztott fájl.")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_IMAGE_EXT:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Csak képfájl tölthető fel (jpg, png, gif, webp).",
        )
    body = await file.read()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Üres fájl.")
    if len(body) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="A kép túl nagy — legfeljebb 8 MB engedélyezett.",
        )
    if not content_type_ok_image(file.content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="A feltöltött fájl MIME típusa nem engedélyezett képhez (jpeg, png, gif, webp).",
        )
    if not image_magic_matches(body):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="A fájl tartalma nem egyezik egy engedélyezett képformátummal — ellenőrizd a fájlt.",
        )

    dest_dir = uploads_dir_for(subdir)
    stem = safe_stem(file.filename, "kep")
    prefix = re.sub(r"[^a-zA-Z0-9_-]+", "-", filename_prefix).strip("-") or "img"
    final_name = f"{prefix}-{stem}-{uuid.uuid4().hex[:10]}{suffix}"
    dest = (dest_dir / final_name).resolve()
    try:
        dest.relative_to(UPLOADS_ROOT)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Érvénytelen fájlnév.") from None
    dest.write_bytes(body)
    return public_url_for(subdir, final_name), final_name


def is_managed_image_url(url: str | None) -> bool:
    s = (url or "").strip()
    return bool(s.startswith(PUBLIC_UPLOAD_PREFIX + "/"))


def _safe_file_under(root: Path, rel: str) -> bool:
    if not rel or ".." in rel or rel.startswith("/"):
        return False
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return path.is_file()


def _resolved_public_media_path(url: str) -> Path | None:
    u = url.strip()
    if not u.startswith("/"):
        return None
    if u.startswith(PUBLIC_UPLOAD_PREFIX + "/"):
        rel = u[len(PUBLIC_UPLOAD_PREFIX) :].lstrip("/")
        if not _safe_file_under(UPLOADS_ROOT, rel):
            return None
        return (UPLOADS_ROOT / rel).resolve()
    rel = u.lstrip("/")
    if not _safe_file_under(FRONTEND_ROOT, rel):
        return None
    return (FRONTEND_ROOT / rel).resolve()


# Tiny 1x1 PNG stubs (e.g. old test seeds) are not useful in the public gallery UI.
_MIN_DISPLAYABLE_IMAGE_BYTES = 120


def local_public_media_exists(url: str | None) -> bool:
    """True ha a URL külső https, vagy helyi uploads / frontend statikus fájlra mutat."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if not u:
        return False
    if u.startswith("http://") or u.startswith("https://"):
        return True
    if not u.startswith("/"):
        return False
    if u.startswith(PUBLIC_UPLOAD_PREFIX + "/"):
        rel = u[len(PUBLIC_UPLOAD_PREFIX) :].lstrip("/")
        return _safe_file_under(UPLOADS_ROOT, rel)
    rel = u.lstrip("/")
    return _safe_file_under(FRONTEND_ROOT, rel)


def local_public_media_displayable(url: str | None) -> bool:
    """File exists, valid image header, and large enough to show (not empty 1x1 placeholders)."""
    if not local_public_media_exists(url):
        return False
    u = (url or "").strip()
    if u.startswith("http://") or u.startswith("https://"):
        return True
    path = _resolved_public_media_path(u)
    if path is None:
        return False
    try:
        if path.stat().st_size < _MIN_DISPLAYABLE_IMAGE_BYTES:
            return False
        return image_magic_matches(path.read_bytes()[:64])
    except OSError:
        return False
