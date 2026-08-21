"""Regression tests: storybook cover image must stay separate from page images.

Covers the mesencsi.hu bug report: cover image not persisting reliably, and a
suspicion that cover_image and page_image were coupled/mapped together.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from image_upload import UPLOADS_ROOT
from mesencsi import app
from tests.helpers import MINIMAL_PNG_BYTES, admin_headers

_PNG_A = MINIMAL_PNG_BYTES
# A second, distinct 1x1 PNG (different pixel colour) so replacement uploads are byte-distinguishable.
_PNG_B = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
    "de0000000c4944415478da6360606060000000050001a5f645400000000049454e44ae426082"
)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _create_book(client: TestClient, headers: dict, title: str = "Fedlap teszt") -> dict:
    r = client.post("/admin/storybooks", json={"title": title}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _upload_cover(client: TestClient, book_id: int, headers: dict, blob: bytes = _PNG_A) -> dict:
    files = {"file": ("cover.png", io.BytesIO(blob), "image/png")}
    r = client.post(f"/admin/storybooks/{book_id}/cover", files=files, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _add_page(client: TestClient, book_id: int, headers: dict) -> dict:
    r = client.post(f"/admin/storybooks/{book_id}/pages", json={"body_text": "Egyszer volt…"}, headers=headers)
    assert r.status_code == 201, r.text
    pages = r.json()["pages"]
    return pages[-1]


def _upload_page_image(client: TestClient, book_id: int, page_id: int, headers: dict, blob: bytes = _PNG_B) -> dict:
    files = {"file": ("page.png", io.BytesIO(blob), "image/png")}
    r = client.post(f"/admin/storybooks/{book_id}/pages/{page_id}/image", files=files, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _publish(client: TestClient, book_id: int, headers: dict) -> None:
    r = client.patch(f"/admin/storybooks/{book_id}", json={"is_published": True}, headers=headers)
    assert r.status_code == 200, r.text


def test_create_storybook_with_cover(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    assert book["cover_image_url"] is None

    upload = _upload_cover(client, book["id"], headers)
    assert upload["url"].startswith("/media/uploads/storybooks/")

    got = client.get(f"/admin/storybooks/{book['id']}", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["cover_image_url"] == upload["url"]

    # Admin list must reflect the same cover — this is what the admin dashboard card renders.
    listing = client.get("/admin/storybooks", headers=headers)
    assert listing.status_code == 200, listing.text
    row = next(b for b in listing.json() if b["id"] == book["id"])
    assert row["cover_image_url"] == upload["url"]

    _publish(client, book["id"], headers)
    pub_list = client.get("/storybooks")
    assert pub_list.status_code == 200, pub_list.text
    pub_row = next(b for b in pub_list.json() if b["id"] == book["id"])
    assert pub_row["cover_image_url"] == upload["url"]

    pub_detail = client.get(f"/storybooks/{book['slug']}")
    assert pub_detail.status_code == 200, pub_detail.text
    assert pub_detail.json()["cover_image_url"] == upload["url"]


def test_replace_cover(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)

    first = _upload_cover(client, book["id"], headers, blob=_PNG_A)
    first_path = UPLOADS_ROOT / first["url"].removeprefix("/media/uploads/")
    assert first_path.is_file()

    second = _upload_cover(client, book["id"], headers, blob=_PNG_B)
    assert second["url"] != first["url"]

    # Old cover file is cleaned up; new one persists.
    assert not first_path.is_file()
    second_path = UPLOADS_ROOT / second["url"].removeprefix("/media/uploads/")
    assert second_path.is_file()

    got = client.get(f"/admin/storybooks/{book['id']}", headers=headers)
    assert got.json()["cover_image_url"] == second["url"]


def test_remove_cover(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    upload = _upload_cover(client, book["id"], headers)
    cover_path = UPLOADS_ROOT / upload["url"].removeprefix("/media/uploads/")
    assert cover_path.is_file()

    r = client.delete(f"/admin/storybooks/{book['id']}/cover", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["cover_image_url"] is None
    assert not cover_path.is_file()

    # Persists after reload — not just in the response of the delete call.
    got = client.get(f"/admin/storybooks/{book['id']}", headers=headers)
    assert got.json()["cover_image_url"] is None

    listing = client.get("/admin/storybooks", headers=headers)
    row = next(b for b in listing.json() if b["id"] == book["id"])
    assert row["cover_image_url"] is None

    _publish(client, book["id"], headers)
    pub_detail = client.get(f"/storybooks/{book['slug']}")
    assert pub_detail.json()["cover_image_url"] is None


def test_page_with_no_image_stays_empty_even_with_cover_set(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    cover = _upload_cover(client, book["id"], headers)
    page = _add_page(client, book["id"], headers)

    got = client.get(f"/admin/storybooks/{book['id']}", headers=headers)
    row_page = next(p for p in got.json()["pages"] if p["id"] == page["id"])
    assert row_page["image_url"] is None
    assert row_page["image_url"] != cover["url"]

    _publish(client, book["id"], headers)
    pub_detail = client.get(f"/storybooks/{book['slug']}")
    pub_page = pub_detail.json()["pages"][0]
    assert pub_page["image_url"] is None


def test_page_with_explicit_image_differs_from_cover(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    cover = _upload_cover(client, book["id"], headers, blob=_PNG_A)
    page = _add_page(client, book["id"], headers)
    page_img = _upload_page_image(client, book["id"], page["id"], headers, blob=_PNG_B)

    assert page_img["url"] != cover["url"]

    got = client.get(f"/admin/storybooks/{book['id']}", headers=headers)
    body = got.json()
    assert body["cover_image_url"] == cover["url"]
    row_page = next(p for p in body["pages"] if p["id"] == page["id"])
    assert row_page["image_url"] == page_img["url"]

    _publish(client, book["id"], headers)
    pub_detail = client.get(f"/storybooks/{book['slug']}").json()
    assert pub_detail["cover_image_url"] == cover["url"]
    assert pub_detail["pages"][0]["image_url"] == page_img["url"]


def test_cover_never_leaks_into_any_page_image(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    cover = _upload_cover(client, book["id"], headers)

    page1 = _add_page(client, book["id"], headers)
    page2 = _add_page(client, book["id"], headers)
    page3 = _add_page(client, book["id"], headers)
    page_img = _upload_page_image(client, book["id"], page2["id"], headers, blob=_PNG_B)

    got = client.get(f"/admin/storybooks/{book['id']}", headers=headers).json()
    by_id = {p["id"]: p for p in got["pages"]}
    assert by_id[page1["id"]]["image_url"] is None
    assert by_id[page2["id"]]["image_url"] == page_img["url"]
    assert by_id[page3["id"]]["image_url"] is None

    for p in got["pages"]:
        assert p["image_url"] != cover["url"], (
            f"page {p['id']} image_url leaked the book cover image"
        )

    _publish(client, book["id"], headers)
    pub_pages = client.get(f"/storybooks/{book['slug']}").json()["pages"]
    pub_by_idx = {p["page_index"]: p for p in pub_pages}
    assert pub_by_idx[1]["image_url"] is None
    assert pub_by_idx[2]["image_url"] == page_img["url"]
    assert pub_by_idx[3]["image_url"] is None
