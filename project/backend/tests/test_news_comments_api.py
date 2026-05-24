"""HTTP integráció: hírkomment POST/GET, flood guard, láthatóság."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from database import SessionLocal
from db_models import NewsComment
from mesencsi import app
from tests.helpers import auth_headers, seed_published_news, seed_unverified_user, seed_verified_user


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_empty_comment_rejected(client: TestClient) -> None:
    uid = seed_verified_user(email="commenter@example.com", username="commenter")
    nid = seed_published_news(slug="comment-empty")
    r = client.post(
        f"/news/{nid}/comments",
        json={"content": " "},
        headers=auth_headers(uid),
    )
    assert r.status_code == 422, r.text


def test_valid_comment_created_and_listed(client: TestClient) -> None:
    uid = seed_verified_user(email="commenter2@example.com", username="commenter2")
    nid = seed_published_news(slug="comment-valid")
    body = {"content": "Szép hír, köszönöm!"}
    created = client.post(f"/news/{nid}/comments", json=body, headers=auth_headers(uid))
    assert created.status_code == 201, created.text
    assert created.json()["content"] == body["content"]

    listed = client.get(f"/news/{nid}/comments?page=1&page_size=20")
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert any(c["content"] == body["content"] for c in items)


def test_hidden_comment_not_in_public_list(client: TestClient) -> None:
    uid = seed_verified_user(email="commenter3@example.com", username="commenter3")
    nid = seed_published_news(slug="comment-hidden")
    db = SessionLocal()
    try:
        db.add(
            NewsComment(
                news_id=nid,
                user_id=uid,
                content="Rejtett moderációs teszt",
                is_visible=False,
            )
        )
        db.commit()
    finally:
        db.close()

    listed = client.get(f"/news/{nid}/comments")
    assert listed.status_code == 200, listed.text
    assert not any("Rejtett" in (c.get("content") or "") for c in listed.json()["items"])


def test_comment_flood_guard_blocks_rapid_second_post(client: TestClient) -> None:
    uid = seed_verified_user(email="flooder@example.com", username="flooder")
    nid = seed_published_news(slug="comment-flood")
    h = auth_headers(uid)
    first = client.post(f"/news/{nid}/comments", json={"content": "Első hozzászólás"}, headers=h)
    assert first.status_code == 201, first.text
    second = client.post(f"/news/{nid}/comments", json={"content": "Második túl gyorsan"}, headers=h)
    assert second.status_code == 429, second.text
    assert "várj" in second.json().get("detail", "").lower() or "gyorsan" in second.json().get("detail", "").lower()


def test_unverified_user_cannot_post_comment(client: TestClient) -> None:
    uid = seed_unverified_user(email="unverified-comment@example.com", username="unverifiedcomment")
    nid = seed_published_news(slug="comment-unverified")
    r = client.post(
        f"/news/{nid}/comments",
        json={"content": "Nem kellene engedni"},
        headers=auth_headers(uid),
    )
    assert r.status_code == 403, r.text
    assert "e-mail" in r.json().get("detail", "").lower()


def test_comment_requires_auth(client: TestClient) -> None:
    nid = seed_published_news(slug="comment-auth")
    r = client.post(f"/news/{nid}/comments", json={"content": "Névtelen"})
    assert r.status_code == 401, r.text


def test_comment_count_on_news_list_and_featured(client: TestClient) -> None:
    uid = seed_verified_user(email="counter@example.com", username="counter")
    nid = seed_published_news(slug="comment-count")
    client.post(
        f"/news/{nid}/comments",
        json={"content": "Számláló teszt"},
        headers=auth_headers(uid),
    )
    listed = client.get("/news?page=1&page_size=10")
    assert listed.status_code == 200, listed.text
    row = next((x for x in listed.json()["items"] if x["id"] == nid), None)
    assert row is not None
    assert row["comment_count"] == 1

    featured = client.get("/news/featured")
    assert featured.status_code == 200, featured.text
    if featured.json() and featured.json().get("id") == nid:
        assert featured.json()["comment_count"] == 1
