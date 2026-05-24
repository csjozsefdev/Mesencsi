"""HTTP integráció: admin képfeltöltés (save_uploaded_image útvonal)."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from image_upload import UPLOADS_ROOT
from mesencsi import app
from tests.helpers import MINIMAL_PNG_BYTES, admin_headers


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_admin_gallery_upload_valid_png(client: TestClient) -> None:
    files = {"file": ("photo.png", io.BytesIO(MINIMAL_PNG_BYTES), "image/png")}
    r = client.post("/admin/gallery/upload", files=files, headers=admin_headers())
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["url"].startswith("/media/uploads/gallery/")
    assert data["filename"]
    path = UPLOADS_ROOT / "gallery" / data["filename"]
    assert path.is_file()


def test_admin_gallery_upload_rejects_invalid_type(client: TestClient) -> None:
    files = {"file": ("notes.txt", io.BytesIO(b"not an image"), "text/plain")}
    r = client.post("/admin/gallery/upload", files=files, headers=admin_headers())
    assert r.status_code == 415, r.text


def test_admin_gallery_upload_rejects_oversized_file(client: TestClient) -> None:
    huge = b"\xff\xd8\xff" + (b"x" * (8 * 1024 * 1024 + 1))
    files = {"file": ("big.jpg", io.BytesIO(huge), "image/jpeg")}
    r = client.post("/admin/gallery/upload", files=files, headers=admin_headers())
    assert r.status_code == 413, r.text


def test_admin_gallery_upload_safe_filename_no_path_traversal(client: TestClient) -> None:
    files = {
        "file": ("../../evil.png", io.BytesIO(MINIMAL_PNG_BYTES), "image/png"),
    }
    r = client.post("/admin/gallery/upload", files=files, headers=admin_headers())
    assert r.status_code == 200, r.text
    fn = r.json()["filename"]
    assert ".." not in fn
    assert (UPLOADS_ROOT / "gallery" / fn).resolve().is_relative_to(UPLOADS_ROOT.resolve())
