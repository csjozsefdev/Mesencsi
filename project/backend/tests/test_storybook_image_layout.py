"""Storybook page image layout metadata — API persistence."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import DigitalStorybook, DigitalStorybookPage
from mesencsi import app
from tests.helpers import admin_headers


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _seed_book_with_page() -> tuple[int, int]:
    db = SessionLocal()
    try:
        book = DigitalStorybook(
            title="Layout teszt",
            slug="layout-teszt-book",
            description=None,
            cover_image_url=None,
            is_published=False,
            animation_settings={},
        )
        db.add(book)
        db.flush()
        page = DigitalStorybookPage(
            book_id=book.id,
            page_index=1,
            title="Első lap",
            body_text="Szöveg",
            image_url="/media/uploads/storybooks/1/page-1-test.jpg",
        )
        db.add(page)
        db.commit()
        db.refresh(book)
        db.refresh(page)
        return int(book.id), int(page.id)
    finally:
        db.close()


def test_storybook_page_image_layout_persists(client: TestClient) -> None:
    book_id, page_id = _seed_book_with_page()
    headers = admin_headers(role="owner")
    r = client.patch(
        f"/admin/storybooks/{book_id}/pages/{page_id}",
        json={
            "image_x_percent": 12.5,
            "image_y_percent": 8.0,
            "image_width_percent": 70.0,
            "image_height_percent": 30.0,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    pages = r.json().get("pages") or []
    row = next(p for p in pages if p["id"] == page_id)
    assert row["image_x_percent"] == 12.5
    assert row["image_y_percent"] == 8.0
    assert row["image_width_percent"] == 70.0
    assert row["image_height_percent"] == 30.0

    pub = client.get("/storybooks/layout-teszt-book")
    if pub.status_code == 404:
        client.patch(
            f"/admin/storybooks/{book_id}",
            json={"is_published": True},
            headers=headers,
        )
        pub = client.get("/storybooks/layout-teszt-book")
    assert pub.status_code == 200, pub.text
    pub_page = pub.json()["pages"][0]
    assert pub_page["image_x_percent"] == 12.5
    assert pub_page["image_width_percent"] == 70.0
