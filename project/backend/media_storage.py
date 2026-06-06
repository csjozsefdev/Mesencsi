"""
Media storage abstraction.

Supports:
- local filesystem under backend/media/uploads (dev/default)
- S3-compatible object storage (R2/S3/etc.) for production durability
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

_log = logging.getLogger("mesencsi.media_storage")


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def media_storage_mode() -> str:
    """'local' (default) or 's3'."""
    raw = _env("MEDIA_STORAGE")
    return (raw.lower() if raw else "local").strip() or "local"


def media_public_base_url() -> str:
    """
    Public base URL for media objects when using S3 storage.

    Example:
      MEDIA_PUBLIC_BASE_URL=https://cdn.example.com
    Then stored keys become: https://cdn.example.com/<key>
    """
    return _env("MEDIA_PUBLIC_BASE_URL").rstrip("/")


def _s3_endpoint_url() -> str | None:
    v = _env("S3_ENDPOINT_URL")
    return v or None


def _s3_bucket() -> str:
    return _env("S3_BUCKET")


def _s3_region() -> str | None:
    v = _env("S3_REGION")
    return v or None


def _s3_prefix() -> str:
    """Optional key prefix inside the bucket (e.g. 'mesencsi')."""
    return _env("S3_KEY_PREFIX").strip().strip("/")


def _join_key(*parts: str) -> str:
    cleaned: list[str] = []
    for p in parts:
        s = str(p).strip().replace("\\", "/").strip("/")
        if s:
            cleaned.append(s)
    return "/".join(cleaned)


def build_object_key(*, subdir: str, filename: str) -> str:
    prefix = _s3_prefix()
    # Keep compatibility with current public path semantics: /media/uploads/<subdir>/<filename>
    # by using an object key rooted at "uploads/".
    return _join_key(prefix, "uploads", subdir, filename)


def url_to_object_key(url: str) -> str | None:
    """
    Map a public media URL back to its storage key.

    Only supports MEDIA_PUBLIC_BASE_URL-based URLs, so we never delete arbitrary external URLs.
    """
    base = media_public_base_url()
    if not base:
        return None
    u = (url or "").strip()
    if not u:
        return None
    if not u.startswith(base + "/"):
        return None
    path = u[len(base) :].lstrip("/")
    if not path or ".." in path:
        return None
    return path


@dataclass(frozen=True)
class StoredObject:
    public_url: str
    key: str


def _require_public_base_for_s3() -> str:
    base = media_public_base_url()
    if not base:
        raise ValueError("MEDIA_PUBLIC_BASE_URL must be set when MEDIA_STORAGE=s3")
    p = urlparse(base)
    if p.scheme not in ("https", "http") or not p.netloc:
        raise ValueError("MEDIA_PUBLIC_BASE_URL must be an absolute http(s) URL")
    return base


def put_bytes(
    *,
    key: str,
    body: bytes,
    content_type: str | None = None,
) -> None:
    mode = media_storage_mode()
    if mode == "local":
        raise RuntimeError("put_bytes is only available for MEDIA_STORAGE=s3")
    if mode != "s3":
        raise RuntimeError(f"Unknown MEDIA_STORAGE mode: {mode!r}")

    import boto3

    bucket = _s3_bucket()
    if not bucket:
        raise ValueError("S3_BUCKET must be set when MEDIA_STORAGE=s3")

    client = boto3.client(
        "s3",
        endpoint_url=_s3_endpoint_url(),
        region_name=_s3_region(),
    )
    extra: dict[str, str] = {}
    if content_type:
        extra["ContentType"] = content_type.split(";")[0].strip()
    client.put_object(Bucket=bucket, Key=key, Body=body, **extra)


def delete_key(key: str) -> None:
    mode = media_storage_mode()
    if mode == "local":
        raise RuntimeError("delete_key is only available for MEDIA_STORAGE=s3")
    if mode != "s3":
        raise RuntimeError(f"Unknown MEDIA_STORAGE mode: {mode!r}")

    import boto3

    bucket = _s3_bucket()
    if not bucket:
        raise ValueError("S3_BUCKET must be set when MEDIA_STORAGE=s3")
    client = boto3.client(
        "s3",
        endpoint_url=_s3_endpoint_url(),
        region_name=_s3_region(),
    )
    client.delete_object(Bucket=bucket, Key=key)


def store_upload_bytes(
    *,
    subdir: str,
    filename: str,
    body: bytes,
    content_type: str | None,
) -> StoredObject:
    """
    Store bytes and return a stable public URL.

    Local mode returns a /media/uploads/... URL (served by FastAPI StaticFiles).
    S3 mode returns MEDIA_PUBLIC_BASE_URL/<key>.
    """
    mode = media_storage_mode()
    if mode == "local":
        # Local writes are handled by image_upload.py; this helper is for s3 mode.
        raise RuntimeError("store_upload_bytes is only used for MEDIA_STORAGE=s3")
    if mode != "s3":
        raise RuntimeError(f"Unknown MEDIA_STORAGE mode: {mode!r}")

    base = _require_public_base_for_s3()
    key = build_object_key(subdir=subdir, filename=filename)
    put_bytes(key=key, body=body, content_type=content_type)
    return StoredObject(public_url=f"{base}/{key}", key=key)

