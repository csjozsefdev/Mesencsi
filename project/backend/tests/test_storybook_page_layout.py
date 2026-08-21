"""Storybook page layout redesign: image_placement enum + safe character limits.

Covers the "no vignette, owner-controlled placement, text can never overflow"
redesign: simple-mode pages (no free-position drag) get a hard, honest
character limit (600 text-only / 150 with an image); the free-position
"advanced" system remains unrestricted, matching the owner's explicit choice.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import DigitalStorybook, DigitalStorybookPage
from mesencsi import app
from models import STORYBOOK_TEXT_ONLY_MAX_CHARS, STORYBOOK_TEXT_WITH_IMAGE_MAX_CHARS
from tests.helpers import MINIMAL_PNG_BYTES, admin_headers


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _create_book(client: TestClient, headers: dict, title: str = "Rétegteszt") -> dict:
    r = client.post("/admin/storybooks", json={"title": title}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _add_page(client: TestClient, book_id: int, headers: dict, body_text: str = "") -> dict:
    r = client.post(f"/admin/storybooks/{book_id}/pages", json={"body_text": body_text}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["pages"][-1]


def _upload_page_image(client: TestClient, book_id: int, page_id: int, headers: dict) -> dict:
    files = {"file": ("page.png", io.BytesIO(MINIMAL_PNG_BYTES), "image/png")}
    r = client.post(f"/admin/storybooks/{book_id}/pages/{page_id}/image", files=files, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _publish(client: TestClient, book_id: int, headers: dict) -> None:
    r = client.patch(f"/admin/storybooks/{book_id}", json={"is_published": True}, headers=headers)
    assert r.status_code == 200, r.text


def test_text_only_page_has_no_placement(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers, body_text="Egyszer volt, hol nem volt…")

    assert page["image_url"] is None
    assert page["image_placement"] == "none"

    _publish(client, book["id"], headers)
    pub_page = client.get(f"/storybooks/{book['slug']}").json()["pages"][0]
    assert pub_page["image_url"] is None
    assert pub_page["image_placement"] == "none"


@pytest.mark.parametrize("placement", ["left", "right", "above", "below"])
def test_image_placement_persists(client: TestClient, placement: str) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers, body_text="Rövid szöveg.")
    upload = _upload_page_image(client, book["id"], page["id"], headers)

    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"image_placement": placement},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    row = next(p for p in r.json()["pages"] if p["id"] == page["id"])
    assert row["image_placement"] == placement
    assert row["image_url"] == upload["url"]

    _publish(client, book["id"], headers)
    pub_page = client.get(f"/storybooks/{book['slug']}").json()["pages"][0]
    assert pub_page["image_placement"] == placement
    assert pub_page["image_url"] == upload["url"]


def test_removing_image_normalizes_placement_to_none(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers, body_text="Szöveg.")
    _upload_page_image(client, book["id"], page["id"], headers)
    client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"image_placement": "above"},
        headers=headers,
    )

    r = client.delete(f"/admin/storybooks/{book['id']}/pages/{page['id']}/image", headers=headers)
    assert r.status_code == 200, r.text
    row = next(p for p in r.json()["pages"] if p["id"] == page["id"])
    assert row["image_url"] is None
    assert row["image_placement"] == "none"


def test_text_only_exact_limit_ok(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    body = "a" * STORYBOOK_TEXT_ONLY_MAX_CHARS

    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"body_text": body},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    row = next(p for p in r.json()["pages"] if p["id"] == page["id"])
    assert len(row["body_text"]) == STORYBOOK_TEXT_ONLY_MAX_CHARS


def test_text_only_one_over_limit_rejected(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    body = "a" * (STORYBOOK_TEXT_ONLY_MAX_CHARS + 1)

    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"body_text": body},
        headers=headers,
    )
    assert r.status_code == 422, r.text
    assert "maximális szöveghosszt" in r.json()["detail"]


def test_with_image_exact_limit_ok(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    _upload_page_image(client, book["id"], page["id"], headers)
    body = "a" * STORYBOOK_TEXT_WITH_IMAGE_MAX_CHARS

    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"body_text": body},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_with_image_one_over_limit_rejected(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    _upload_page_image(client, book["id"], page["id"], headers)
    body = "a" * (STORYBOOK_TEXT_WITH_IMAGE_MAX_CHARS + 1)

    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"body_text": body},
        headers=headers,
    )
    assert r.status_code == 422, r.text
    assert "maximális szöveghosszt" in r.json()["detail"]


def test_image_upload_rejected_when_text_already_too_long_for_image(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    body = "a" * (STORYBOOK_TEXT_WITH_IMAGE_MAX_CHARS + 1)
    page = _add_page(client, book["id"], headers, body_text=body)

    files = {"file": ("page.png", io.BytesIO(MINIMAL_PNG_BYTES), "image/png")}
    r = client.post(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}/image", files=files, headers=headers
    )
    assert r.status_code == 422, r.text

    got = client.get(f"/admin/storybooks/{book['id']}", headers=headers)
    row = next(p for p in got.json()["pages"] if p["id"] == page["id"])
    assert row["image_url"] is None


def test_advanced_free_position_page_is_unrestricted(client: TestClient) -> None:
    """Pages using the free-position drag system stay unlimited — owner's explicit choice."""
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)

    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"text_x_percent": 50.0, "text_y_percent": 50.0},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    long_body = "a" * (STORYBOOK_TEXT_ONLY_MAX_CHARS + 500)
    r2 = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"body_text": long_body},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    row = next(p for p in r2.json()["pages"] if p["id"] == page["id"])
    assert len(row["body_text"]) == len(long_body)


def test_legacy_overlimit_content_not_truncated_and_not_bricked(client: TestClient) -> None:
    """A pre-existing page longer than the new limit must still be readable in
    full (no silent truncation) and unrelated edits to it must not be blocked."""
    db = SessionLocal()
    try:
        book = DigitalStorybook(
            title="Régi könyv",
            slug="regi-konyv-layout",
            description=None,
            cover_image_url=None,
            is_published=True,
            animation_settings={},
        )
        db.add(book)
        db.flush()
        long_body = "b" * (STORYBOOK_TEXT_ONLY_MAX_CHARS + 900)
        page = DigitalStorybookPage(
            book_id=book.id,
            page_index=1,
            body_text=long_body,
            image_placement="none",
        )
        db.add(page)
        db.commit()
        db.refresh(book)
        db.refresh(page)
        book_id, page_id, expected_len = book.id, page.id, len(long_body)
    finally:
        db.close()

    headers = admin_headers(role="owner")
    client = TestClient(app)
    with client:
        got = client.get(f"/admin/storybooks/{book_id}", headers=headers)
        assert got.status_code == 200, got.text
        row = next(p for p in got.json()["pages"] if p["id"] == page_id)
        assert len(row["body_text"]) == expected_len

        pub = client.get("/storybooks/regi-konyv-layout")
        assert pub.status_code == 200, pub.text
        assert len(pub.json()["pages"][0]["body_text"]) == expected_len

        # Unrelated field edit (not touching body_text/image_placement) must still work.
        r = client.patch(
            f"/admin/storybooks/{book_id}/pages/{page_id}",
            json={"title": "Cím"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        row2 = next(p for p in r.json()["pages"] if p["id"] == page_id)
        assert len(row2["body_text"]) == expected_len
        assert row2["title"] == "Cím"
