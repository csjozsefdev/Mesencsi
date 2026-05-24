"""HTTP integráció: publikus GET /gallery."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from tests.helpers import seed_gallery_items


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_gallery_empty_list_ok(client: TestClient) -> None:
    r = client.get("/gallery?page=1&page_size=12")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["pages"] == 0


def test_gallery_pagination(client: TestClient) -> None:
    seed_gallery_items(3)
    p1 = client.get("/gallery?page=1&page_size=2")
    assert p1.status_code == 200, p1.text
    d1 = p1.json()
    assert d1["total"] == 3
    assert len(d1["items"]) == 2
    assert d1["pages"] == 2

    p2 = client.get("/gallery?page=2&page_size=2")
    assert p2.status_code == 200, p2.text
    d2 = p2.json()
    assert len(d2["items"]) == 1
    assert d1["items"][0]["id"] != d2["items"][0]["id"]


def test_gallery_page_two_invalid_when_only_one_page(client: TestClient) -> None:
    seed_gallery_items(3)
    r = client.get("/gallery?page=2&page_size=12")
    assert r.status_code == 422, r.text


def test_gallery_invalid_page_returns_422(client: TestClient) -> None:
    seed_gallery_items(1)
    r = client.get("/gallery?page=99&page_size=12")
    assert r.status_code == 422, r.text


def test_gallery_item_by_id(client: TestClient) -> None:
    ids = seed_gallery_items(1)
    r = client.get(f"/gallery/{ids[0]}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == ids[0]


def test_gallery_missing_item_404(client: TestClient) -> None:
    assert client.get("/gallery/999999").status_code == 404


def test_gallery_includes_frontend_static_image_url(client: TestClient) -> None:
    from database import SessionLocal
    from db_models import GalleryItem
    from frontend_assets import page_background_asset_path

    bg = page_background_asset_path()
    if not bg.is_file():
        import pytest

        pytest.skip("frontend/images/mesencsi-bg.jpg hiányzik")

    db = SessionLocal()
    try:
        db.add(
            GalleryItem(
                title="Háttér",
                image_url="/images/mesencsi-bg.jpg",
                description=None,
                sort_order=0,
            )
        )
        db.commit()
    finally:
        db.close()

    r = client.get("/gallery?page=1&page_size=12")
    assert r.status_code == 200, r.text
    urls = [it["image_url"] for it in r.json()["items"]]
    assert "/images/mesencsi-bg.jpg" in urls


def test_gallery_omits_tiny_placeholder_files(client: TestClient) -> None:
    from image_upload import public_url_for, uploads_dir_for

    from tests.helpers import MINIMAL_PNG_BYTES

    seed_gallery_items(1)
    gallery_dir = uploads_dir_for("gallery")
    (gallery_dir / "tiny-stub.png").write_bytes(MINIMAL_PNG_BYTES)
    from database import SessionLocal
    from db_models import GalleryItem

    db = SessionLocal()
    try:
        db.add(
            GalleryItem(
                title="Tiny stub",
                image_url=public_url_for("gallery", "tiny-stub.png"),
                description=None,
                sort_order=50,
            )
        )
        db.commit()
    finally:
        db.close()

    r = client.get("/gallery?page=1&page_size=50")
    assert r.status_code == 200, r.text
    titles = [it["title"] for it in r.json()["items"]]
    assert "Tiny stub" not in titles


def test_gallery_omits_rows_without_file_on_disk(client: TestClient) -> None:
    from database import SessionLocal
    from db_models import GalleryItem

    seed_gallery_items(1)
    db = SessionLocal()
    try:
        db.add(
            GalleryItem(
                title="Hiányzó fájl",
                image_url="/media/uploads/gallery/nem-letezo.png",
                description=None,
                sort_order=99,
            )
        )
        db.commit()
    finally:
        db.close()

    r = client.get("/gallery?page=1&page_size=12")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Kép 1"
