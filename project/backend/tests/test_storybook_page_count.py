"""V3.4: proves the page-count business limit has been removed.

The only page-count enforcement that ever existed was `_MAX_PAGES_PER_BOOK`
in routers/storybooks_admin.py (a constant of 80, never 8, confirmed via git
history) — deleted outright per the owner's explicit "no ceiling" decision.
These tests replace that removed limit with proof that page creation, edit,
persistence, reorder, and delete all keep working well past where any old
cap could plausibly have mattered, exercised through the real admin API
(not a bare helper), plus the public reader for pages beyond index 7.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from tests.helpers import admin_headers


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _create_book(client: TestClient, headers: dict, title: str = "Sok oldalas mesekönyv") -> dict:
    r = client.post("/admin/storybooks", json={"title": title}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _add_page(client: TestClient, book_id: int, headers: dict, body_text: str = "") -> dict:
    r = client.post(f"/admin/storybooks/{book_id}/pages", json={"body_text": body_text}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["pages"][-1]


def _add_n_pages(client: TestClient, book_id: int, headers: dict, n: int) -> dict:
    book = None
    for i in range(1, n + 1):
        r = client.post(
            f"/admin/storybooks/{book_id}/pages",
            json={"body_text": f"Oldal {i} szövege"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        book = r.json()
    return book


def _publish(client: TestClient, book_id: int, headers: dict) -> None:
    r = client.patch(f"/admin/storybooks/{book_id}", json={"is_published": True}, headers=headers)
    assert r.status_code == 200, r.text


def test_eight_pages_still_works(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    result = _add_n_pages(client, book["id"], headers, 8)
    assert len(result["pages"]) == 8


def test_ninth_page_can_be_created(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    result = _add_n_pages(client, book["id"], headers, 9)
    assert len(result["pages"]) == 9
    assert result["pages"][8]["body_text"] == "Oldal 9 szövege"


def test_tenth_page_can_be_created(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    result = _add_n_pages(client, book["id"], headers, 10)
    assert len(result["pages"]) == 10


def test_twenty_page_storybook_can_be_stored_and_read(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    _add_n_pages(client, book["id"], headers, 20)

    got = client.get(f"/admin/storybooks/{book['id']}", headers=headers)
    assert got.status_code == 200, got.text
    assert len(got.json()["pages"]) == 20


def test_page_order_preserved_past_eight_pages(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    result = _add_n_pages(client, book["id"], headers, 12)
    texts = [p["body_text"] for p in result["pages"]]
    assert texts == [f"Oldal {i} szövege" for i in range(1, 13)]
    indices = [p["page_index"] for p in result["pages"]]
    assert indices == sorted(indices)


def test_page_nine_plus_can_be_edited_and_persists(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    result = _add_n_pages(client, book["id"], headers, 10)
    page_ten = result["pages"][9]

    layout = {
        "version": 1,
        "objects": [
            {
                "id": "primary-text",
                "type": "text",
                "role": "primary",
                "x": 8,
                "y": 58,
                "w": 50,
                "h": 36,
                "rotation": 0,
                "format": {"fontSize": "m", "bold": False, "italic": False, "underline": False, "align": "left"},
            }
        ],
    }
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page_ten['id']}",
        json={"body_text": "Frissített 10. oldal", "layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    row = next(p for p in r.json()["pages"] if p["id"] == page_ten["id"])
    assert row["body_text"] == "Frissített 10. oldal"
    assert row["layout_json"] == layout

    got = client.get(f"/admin/storybooks/{book['id']}", headers=headers)
    row2 = next(p for p in got.json()["pages"] if p["id"] == page_ten["id"])
    assert row2["body_text"] == "Frissített 10. oldal"
    assert row2["layout_json"] == layout


def test_page_nine_plus_renders_in_public_reader(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    _add_n_pages(client, book["id"], headers, 11)
    _publish(client, book["id"], headers)

    pub = client.get(f"/storybooks/{book['slug']}")
    assert pub.status_code == 200, pub.text
    pub_pages = pub.json()["pages"]
    assert len(pub_pages) == 11
    assert pub_pages[8]["body_text"] == "Oldal 9 szövege"
    assert pub_pages[10]["body_text"] == "Oldal 11 szövege"


def test_deleting_page_above_index_seven_works(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    result = _add_n_pages(client, book["id"], headers, 10)
    page_nine = result["pages"][8]

    r = client.delete(f"/admin/storybooks/{book['id']}/pages/{page_nine['id']}", headers=headers)
    assert r.status_code == 200, r.text
    remaining = [p["body_text"] for p in r.json()["pages"]]
    assert remaining == [f"Oldal {i} szövege" for i in range(1, 10) if i != 9] + ["Oldal 10 szövege"]
    assert len(remaining) == 9


def test_reordering_pages_above_index_seven_works(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    result = _add_n_pages(client, book["id"], headers, 10)
    ids = [p["id"] for p in result["pages"]]
    # Move the 10th page (index 9) to the front — a reorder touching a page
    # well past the old 8-page ceiling.
    reordered_ids = [ids[9]] + ids[:9]

    r = client.post(
        f"/admin/storybooks/{book['id']}/pages/reorder",
        json={"ordered_page_ids": reordered_ids},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    got_order = [p["id"] for p in r.json()["pages"]]
    assert got_order == reordered_ids
