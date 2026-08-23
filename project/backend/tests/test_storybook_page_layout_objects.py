"""V3 object-canvas editor: layout_json schema/validation on storybook pages.

Covers the additive `layout_json` column added for the free-form drag/resize/
rotate object-canvas editor (text/image/decoration objects). The column is
NULL until an admin explicitly saves a page in the new editor — no bulk
migration, no auto-write. A page with layout_json set is exempt from the
fixed 600/150-char safe-length check the same way today's legacy "advanced"
free-position pages are, since its own live text-overflow fit-check (client
side) is the real safeguard once the box is owner-resizable.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from tests.helpers import MINIMAL_PNG_BYTES, admin_headers


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _create_book(client: TestClient, headers: dict, title: str = "Objektum réteg teszt") -> dict:
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


def _minimal_layout(**overrides) -> dict:
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
    layout.update(overrides)
    return layout


def test_minimal_layout_round_trips(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers, body_text="Rövid szöveg.")

    layout = _minimal_layout()
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    row = next(p for p in r.json()["pages"] if p["id"] == page["id"])
    assert row["layout_json"] == layout

    got = client.get(f"/admin/storybooks/{book['id']}", headers=headers)
    row2 = next(p for p in got.json()["pages"] if p["id"] == page["id"])
    assert row2["layout_json"] == layout


def test_layout_json_null_until_touched(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers, body_text="Szöveg.")
    assert page["layout_json"] is None

    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"title": "Cím"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    row = next(p for p in r.json()["pages"] if p["id"] == page["id"])
    assert row["layout_json"] is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda l: l["objects"][0].pop("x"),
        lambda l: l["objects"][0].__setitem__("x", 150),
        lambda l: l["objects"][0].__setitem__("w", 0),
        lambda l: l["objects"][0].__setitem__("rotation", 200),
        lambda l: l["objects"][0].__setitem__("type", "sparkle"),
        lambda l: l.__setitem__("version", 2),
        lambda l: l.__setitem__("objects", []),
    ],
)
def test_malformed_layout_rejected(client: TestClient, mutate) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    layout = _minimal_layout()
    mutate(layout)

    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 422, r.text


def test_missing_primary_text_object_rejected(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    layout = {
        "version": 1,
        "objects": [
            {"id": "deco-1", "type": "decoration", "x": 2, "y": 2, "w": 8, "h": 8, "rotation": 0,
             "decoration": {"glyph": "⭐"}},
        ],
    }
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 422, r.text


def test_duplicate_primary_text_object_rejected(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    layout = _minimal_layout()
    second = dict(layout["objects"][0])
    second["id"] = "primary-text-2"
    layout["objects"].append(second)

    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 422, r.text


def test_too_many_extra_objects_rejected(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    layout = _minimal_layout()
    for i in range(21):
        layout["objects"].append(
            {
                "id": f"deco-{i}",
                "type": "decoration",
                "x": 1,
                "y": 1,
                "w": 2,
                "h": 2,
                "rotation": 0,
                "decoration": {"glyph": "⭐"},
            }
        )
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 422, r.text


def test_oversized_layout_rejected(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    layout = _minimal_layout()
    layout["objects"][0]["format"]["highlight"] = None
    # Pad with a huge caption to exceed the ~24KB cap without breaching the 20-object cap.
    layout["objects"].append(
        {
            "id": "cap-huge",
            "type": "text",
            "role": "secondary",
            "x": 1,
            "y": 1,
            "w": 2,
            "h": 2,
            "rotation": 0,
            "content": "a" * 2000,
        }
    )
    for i in range(19):
        layout["objects"].append(
            {
                "id": f"cap-{i}",
                "type": "text",
                "role": "secondary",
                "x": 1,
                "y": 1,
                "w": 2,
                "h": 2,
                "rotation": 0,
                "content": "b" * 2000,
            }
        )
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 422, r.text


def test_image_object_without_image_url_rejected(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    layout = _minimal_layout()
    layout["objects"].append(
        {
            "id": "image-1",
            "type": "image",
            "x": 55,
            "y": 5,
            "w": 40,
            "h": 50,
            "rotation": 0,
            "image": {"fit": "contain", "aspectLocked": True},
        }
    )
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 422, r.text
    assert "kép" in r.json()["detail"]


def test_image_object_with_image_url_accepted(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    _upload_page_image(client, book["id"], page["id"], headers)
    layout = _minimal_layout()
    layout["objects"].append(
        {
            "id": "image-1",
            "type": "image",
            "x": 55,
            "y": 5,
            "w": 40,
            "h": 50,
            "rotation": 15,
            "image": {"fit": "contain", "aspectLocked": True},
        }
    )
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_two_image_objects_rejected(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    _upload_page_image(client, book["id"], page["id"], headers)
    layout = _minimal_layout()
    img = {"id": "image-1", "type": "image", "x": 55, "y": 5, "w": 40, "h": 50, "rotation": 0,
           "image": {"fit": "contain", "aspectLocked": True}}
    layout["objects"].append(img)
    layout["objects"].append({**img, "id": "image-2"})

    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 422, r.text


def test_deleting_image_strips_image_object_from_layout(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    _upload_page_image(client, book["id"], page["id"], headers)
    layout = _minimal_layout()
    layout["objects"].append(
        {
            "id": "image-1",
            "type": "image",
            "x": 55,
            "y": 5,
            "w": 40,
            "h": 50,
            "rotation": 0,
            "image": {"fit": "contain", "aspectLocked": True},
        }
    )
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    r2 = client.delete(f"/admin/storybooks/{book['id']}/pages/{page['id']}/image", headers=headers)
    assert r2.status_code == 200, r2.text
    row = next(p for p in r2.json()["pages"] if p["id"] == page["id"])
    assert row["image_url"] is None
    object_types = [o["type"] for o in row["layout_json"]["objects"]]
    assert "image" not in object_types
    assert "text" in object_types


def test_uploading_image_adds_image_object_to_existing_layout_without_one(client: TestClient) -> None:
    """A page can have layout_json saved (e.g. text formatting) before it ever
    gets an image. Uploading one afterwards must add an image object, or the
    upload would set image_url with no object anywhere to render it — since
    resolvePageLayout() uses a non-null layout_json as-is, with no legacy
    fallback."""
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    layout = _minimal_layout()
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    row = next(p for p in r.json()["pages"] if p["id"] == page["id"])
    assert not any(o["type"] == "image" for o in row["layout_json"]["objects"])

    _upload_page_image(client, book["id"], page["id"], headers)

    r2 = client.get(f"/admin/storybooks/{book['id']}", headers=headers)
    assert r2.status_code == 200, r2.text
    row2 = next(p for p in r2.json()["pages"] if p["id"] == page["id"])
    assert row2["image_url"]
    image_objects = [o for o in row2["layout_json"]["objects"] if o["type"] == "image"]
    assert len(image_objects) == 1
    for key in ("x", "y", "w", "h", "rotation"):
        assert key in image_objects[0]

    # A second upload (replacing the image) must not add a duplicate object.
    _upload_page_image(client, book["id"], page["id"], headers)
    r3 = client.get(f"/admin/storybooks/{book['id']}", headers=headers)
    row3 = next(p for p in r3.json()["pages"] if p["id"] == page["id"])
    assert len([o for o in row3["layout_json"]["objects"] if o["type"] == "image"]) == 1


def test_layout_json_page_exempt_from_char_limit(client: TestClient) -> None:
    """Mirrors test_advanced_free_position_page_is_unrestricted for legacy fields —
    a page with layout_json set gets the same char-limit exemption."""
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    layout = _minimal_layout()
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    long_body = "a" * 5000
    r2 = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"body_text": long_body},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    row = next(p for p in r2.json()["pages"] if p["id"] == page["id"])
    assert len(row["body_text"]) == len(long_body)


def test_legacy_page_without_layout_json_still_enforces_char_limit(client: TestClient) -> None:
    """Explicit regression guard: a page that never touched layout_json keeps the
    exact existing 600-char behavior — extends, does not replace, the old check."""
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)

    long_body = "a" * 601
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"body_text": long_body},
        headers=headers,
    )
    assert r.status_code == 422, r.text


def test_public_get_returns_layout_json_verbatim(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers, body_text="Szöveg.")
    layout = _minimal_layout()
    client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    _publish(client, book["id"], headers)

    pub = client.get(f"/storybooks/{book['slug']}")
    assert pub.status_code == 200, pub.text
    assert pub.json()["pages"][0]["layout_json"] == layout


def test_public_get_returns_null_layout_json_when_untouched(client: TestClient) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    _add_page(client, book["id"], headers, body_text="Szöveg.")
    _publish(client, book["id"], headers)

    pub = client.get(f"/storybooks/{book['slug']}")
    assert pub.status_code == 200, pub.text
    assert pub.json()["pages"][0]["layout_json"] is None


@pytest.mark.parametrize("opacity", [0, 0.5, 1])
def test_object_opacity_within_range_accepted(client: TestClient, opacity: float) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    layout = _minimal_layout()
    layout["objects"][0]["opacity"] = opacity
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    row = next(p for p in r.json()["pages"] if p["id"] == page["id"])
    assert row["layout_json"]["objects"][0]["opacity"] == opacity


@pytest.mark.parametrize("opacity", [-0.01, 1.01, 2, -1])
def test_object_opacity_outside_range_rejected(client: TestClient, opacity: float) -> None:
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    layout = _minimal_layout()
    layout["objects"][0]["opacity"] = opacity
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 422, r.text


def test_object_opacity_omitted_defaults_fine(client: TestClient) -> None:
    """opacity is optional — a layout without it (matching every page saved
    before this field existed) must keep validating and saving fine."""
    headers = admin_headers(role="owner")
    book = _create_book(client, headers)
    page = _add_page(client, book["id"], headers)
    layout = _minimal_layout()
    assert "opacity" not in layout["objects"][0]
    r = client.patch(
        f"/admin/storybooks/{book['id']}/pages/{page['id']}",
        json={"layout_json": layout},
        headers=headers,
    )
    assert r.status_code == 200, r.text
