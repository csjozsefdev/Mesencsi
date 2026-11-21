"""Nyitási akció: felhasználói mesekönyv-piszkozatok — a szigorú szabályok bizonyítása.

A legfontosabb: felhasználó SOHA nem publikálhat; a publikálás kizárólag az admin PATCH-e.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from mesencsi import app
from tests.helpers import MINIMAL_PNG_BYTES, admin_headers, auth_headers, seed_unverified_user, seed_verified_user


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_STORYBOOKS_ENABLED", "1")
    monkeypatch.delenv("USER_STORYBOOKS_MAX_BOOKS", raising=False)
    monkeypatch.delenv("USER_STORYBOOKS_MAX_PAGES", raising=False)


@pytest.fixture
def alice() -> dict:
    return auth_headers(seed_verified_user(email="alice@example.com", username="alice"))


@pytest.fixture
def bob() -> dict:
    return auth_headers(seed_verified_user(email="bob@example.com", username="bob"))


def _create(client: TestClient, h: dict, title: str = "Az én mesém") -> dict:
    r = client.post("/my/storybooks", json={"title": title}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _page(client: TestClient, h: dict, book_id: int, text: str = "Egyszer volt...") -> dict:
    r = client.post(f"/my/storybooks/{book_id}/pages", json={"body_text": text}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _submit(client: TestClient, h: dict, book_id: int, **over):
    body = {"author_name": "Kis Mesélő", "consent": True, **over}
    return client.post(f"/my/storybooks/{book_id}/submit", json=body, headers=h)


# ------------------------------------------------------------ kapcsoló és belépés


def test_flag_off_returns_404_and_status_disabled(client: TestClient, alice: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("USER_STORYBOOKS_ENABLED", raising=False)
    assert client.get("/my/storybooks", headers=alice).status_code == 404
    assert client.post("/my/storybooks", json={"title": "x"}, headers=alice).status_code == 404
    st = client.get("/my/storybooks/status")
    assert st.status_code == 200 and st.json()["enabled"] is False


def test_status_enabled(client: TestClient) -> None:
    j = client.get("/my/storybooks/status").json()
    assert j["enabled"] is True and j["max_books"] == 3 and j["max_pages"] == 20


def test_requires_login_and_verified_email(client: TestClient) -> None:
    assert client.get("/my/storybooks").status_code == 401
    unv = auth_headers(seed_unverified_user())
    assert client.get("/my/storybooks", headers=unv).status_code == 403
    assert client.post("/my/storybooks", json={"title": "x"}, headers=unv).status_code == 403


def test_admin_token_is_not_a_user(client: TestClient) -> None:
    assert client.get("/my/storybooks", headers=admin_headers()).status_code == 401


# ------------------------------------------------------------ publikálás tiltása


def test_created_book_is_never_published(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    assert b["is_published"] is False and b["submission_status"] == "draft" and b["can_edit"] is True


def test_user_cannot_publish_via_any_field(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    r = client.patch(f"/my/storybooks/{b['id']}", json={"is_published": True}, headers=alice)
    assert r.status_code == 422
    r = client.patch(f"/my/storybooks/{b['id']}", json={"animation_settings": {"x": 1}}, headers=alice)
    assert r.status_code == 422
    r = client.post("/my/storybooks", json={"title": "x", "is_published": True}, headers=alice)
    assert r.status_code == 422
    assert client.get(f"/my/storybooks/{b['id']}", headers=alice).json()["is_published"] is False
    assert client.get("/storybooks").json() == []


def test_user_cannot_use_admin_endpoints(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    assert client.patch(f"/admin/storybooks/{b['id']}", json={"is_published": True}, headers=alice).status_code in (401, 403)
    assert client.get("/admin/storybook-submissions", headers=alice).status_code in (401, 403)
    assert client.get("/admin/storybook-submissions/pending-count", headers=alice).status_code in (401, 403)


def test_submitted_book_not_public_until_admin_publishes(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    _page(client, alice, b["id"])
    assert _submit(client, alice, b["id"]).status_code == 200
    assert client.get("/storybooks").json() == []
    assert client.get(f"/storybooks/{b['slug']}").status_code == 404
    r = client.patch(f"/admin/storybooks/{b['id']}", json={"is_published": True}, headers=admin_headers())
    assert r.status_code == 200, r.text
    pub = client.get(f"/storybooks/{b['slug']}")
    assert pub.status_code == 200
    assert "Szerző: Kis Mesélő" in (pub.json()["description"] or "")


# ------------------------------------------------------------ tulajdonjog


def test_other_users_book_is_404_everywhere(client: TestClient, alice: dict, bob: dict) -> None:
    b = _create(client, alice)
    p = _page(client, alice, b["id"])["pages"][0]
    bid = b["id"]
    calls = [
        client.get(f"/my/storybooks/{bid}", headers=bob),
        client.patch(f"/my/storybooks/{bid}", json={"title": "hack"}, headers=bob),
        client.delete(f"/my/storybooks/{bid}", headers=bob),
        client.post(f"/my/storybooks/{bid}/pages", json={"body_text": "x"}, headers=bob),
        client.patch(f"/my/storybooks/{bid}/pages/{p['id']}", json={"body_text": "x"}, headers=bob),
        client.delete(f"/my/storybooks/{bid}/pages/{p['id']}", headers=bob),
        client.post(f"/my/storybooks/{bid}/pages/reorder", json={"ordered_page_ids": [p["id"]]}, headers=bob),
        client.post(f"/my/storybooks/{bid}/submit", json={"author_name": "Bob", "consent": True}, headers=bob),
        client.post(f"/my/storybooks/{bid}/withdraw", headers=bob),
    ]
    assert [c.status_code for c in calls] == [404] * len(calls)
    assert client.get("/my/storybooks", headers=bob).json() == []


def test_admin_created_book_is_not_reachable_by_users(client: TestClient, alice: dict) -> None:
    r = client.post("/admin/storybooks", json={"title": "Admin mese"}, headers=admin_headers())
    assert client.get(f"/my/storybooks/{r.json()['id']}", headers=alice).status_code == 404


# ------------------------------------------------------------ állapotgép


def test_submit_requires_consent_and_a_page(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    assert _submit(client, alice, b["id"]).status_code == 422  # nincs oldal
    _page(client, alice, b["id"])
    assert _submit(client, alice, b["id"], consent=False).status_code == 422
    assert client.post(f"/my/storybooks/{b['id']}/submit", json={"consent": True}, headers=alice).status_code == 422
    assert _submit(client, alice, b["id"]).status_code == 200


def test_submitted_book_is_locked_and_withdraw_unlocks(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    p = _page(client, alice, b["id"])["pages"][0]
    sub = _submit(client, alice, b["id"]).json()
    assert sub["submission_status"] == "submitted" and sub["can_edit"] is False
    bid = b["id"]
    assert client.patch(f"/my/storybooks/{bid}", json={"title": "új"}, headers=alice).status_code == 409
    assert client.post(f"/my/storybooks/{bid}/pages", json={"body_text": "x"}, headers=alice).status_code == 409
    assert client.patch(f"/my/storybooks/{bid}/pages/{p['id']}", json={"body_text": "x"}, headers=alice).status_code == 409
    assert client.delete(f"/my/storybooks/{bid}/pages/{p['id']}", headers=alice).status_code == 409
    assert client.delete(f"/my/storybooks/{bid}", headers=alice).status_code == 409
    assert _submit(client, alice, bid).status_code == 409  # kétszer nem
    w = client.post(f"/my/storybooks/{bid}/withdraw", headers=alice)
    assert w.status_code == 200 and w.json()["submission_status"] == "draft" and w.json()["can_edit"] is True
    assert "Szerző:" not in (w.json()["description"] or "")
    assert client.patch(f"/my/storybooks/{bid}", json={"title": "új"}, headers=alice).status_code == 200


def test_published_book_is_locked_and_cannot_be_withdrawn(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    p = _page(client, alice, b["id"])["pages"][0]
    _submit(client, alice, b["id"])
    client.patch(f"/admin/storybooks/{b['id']}", json={"is_published": True}, headers=admin_headers())
    bid = b["id"]
    got = client.get(f"/my/storybooks/{bid}", headers=alice).json()
    assert got["submission_status"] == "published" and got["can_edit"] is False
    assert client.patch(f"/my/storybooks/{bid}/pages/{p['id']}", json={"body_text": "x"}, headers=alice).status_code == 409
    assert client.post(f"/my/storybooks/{bid}/withdraw", headers=alice).status_code == 409
    assert client.delete(f"/my/storybooks/{bid}", headers=alice).status_code == 409


def test_author_marker_not_shown_to_the_author_and_not_duplicated(client: TestClient, alice: dict) -> None:
    b = client.post("/my/storybooks", json={"title": "T", "description": "Rövid leírás"}, headers=alice).json()
    _page(client, alice, b["id"])
    _submit(client, alice, b["id"])
    client.post(f"/my/storybooks/{b['id']}/withdraw", headers=alice)
    _submit(client, alice, b["id"], author_name="Másik Név")
    admin_view = client.get(f"/admin/storybooks/{b['id']}", headers=admin_headers()).json()
    assert admin_view["description"] == "Rövid leírás\n\nSzerző: Másik Név"
    mine = client.get(f"/my/storybooks/{b['id']}", headers=alice).json()
    assert mine["description"] == "Rövid leírás" and mine["author_name"] == "Másik Név"


# ------------------------------------------------------------ korlátok


def test_open_book_limit(client: TestClient, alice: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_STORYBOOKS_MAX_BOOKS", "2")
    first = _create(client, alice, "A")
    _create(client, alice, "B")
    assert client.post("/my/storybooks", json={"title": "C"}, headers=alice).status_code == 409
    # a publikált mese felszabadítja a helyet
    _page(client, alice, first["id"])
    _submit(client, alice, first["id"])
    client.patch(f"/admin/storybooks/{first['id']}", json={"is_published": True}, headers=admin_headers())
    assert client.post("/my/storybooks", json={"title": "C"}, headers=alice).status_code == 201


def test_page_limit(client: TestClient, alice: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_STORYBOOKS_MAX_PAGES", "3")
    b = _create(client, alice)
    for _ in range(3):
        _page(client, alice, b["id"])
    assert client.post(f"/my/storybooks/{b['id']}/pages", json={"body_text": "x"}, headers=alice).status_code == 409


def test_page_text_cap(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    r = client.post(f"/my/storybooks/{b['id']}/pages", json={"body_text": "a" * 6001}, headers=alice)
    assert r.status_code == 422


def test_audio_is_not_available_to_users(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    p = _page(client, alice, b["id"])["pages"][0]
    r = client.post(
        f"/my/storybooks/{b['id']}/pages/{p['id']}/audio",
        files={"file": ("a.mp3", io.BytesIO(b"ID3" + b"\0" * 64), "audio/mpeg")},
        headers=alice,
    )
    assert r.status_code in (404, 405)
    r = client.patch(
        f"/my/storybooks/{b['id']}/pages/{p['id']}",
        json={"audio_url": "https://evil.example/a.mp3", "extra": {"k": 1}, "body_text": "ok"},
        headers=alice,
    )
    assert r.status_code == 200, r.text
    page = r.json()["pages"][0]
    assert not page.get("audio_url") and page["body_text"] == "ok"
    assert not page.get("extra")


def test_image_upload_works_and_is_size_capped(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    p = _page(client, alice, b["id"])["pages"][0]
    ok = client.post(
        f"/my/storybooks/{b['id']}/pages/{p['id']}/image",
        files={"file": ("x.png", io.BytesIO(MINIMAL_PNG_BYTES), "image/png")},
        headers=alice,
    )
    assert ok.status_code == 200, ok.text
    big = client.post(
        f"/my/storybooks/{b['id']}/pages/{p['id']}/image",
        files={"file": ("big.png", io.BytesIO(MINIMAL_PNG_BYTES + b"\0" * (3 * 1024 * 1024 + 10)), "image/png")},
        headers=alice,
    )
    assert big.status_code == 413
    other = auth_headers(seed_verified_user(email="eve@example.com", username="eve"))
    assert (
        client.post(
            f"/my/storybooks/{b['id']}/pages/{p['id']}/image",
            files={"file": ("x.png", io.BytesIO(MINIMAL_PNG_BYTES), "image/png")},
            headers=other,
        ).status_code
        == 404
    )


def test_delete_own_draft(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    assert client.delete(f"/my/storybooks/{b['id']}", headers=alice).status_code == 204
    assert client.get(f"/my/storybooks/{b['id']}", headers=alice).status_code == 404


# ------------------------------------------------------------ admin oldal


def test_admin_pending_count_list_and_return(client: TestClient, alice: dict, bob: dict) -> None:
    adm = admin_headers()
    assert client.get("/admin/storybook-submissions/pending-count", headers=adm).json() == {"pending": 0}
    a = _create(client, alice, "Alice meséje")
    b = _create(client, bob, "Bob meséje")
    _page(client, alice, a["id"])
    _page(client, bob, b["id"])
    _submit(client, alice, a["id"], author_name="Alice")
    assert client.get("/admin/storybook-submissions/pending-count", headers=adm).json() == {"pending": 1}
    _submit(client, bob, b["id"], author_name="Bob")
    assert client.get("/admin/storybook-submissions/pending-count", headers=adm).json() == {"pending": 2}

    items = client.get("/admin/storybook-submissions", headers=adm).json()
    assert {i["author_name"] for i in items} == {"Alice", "Bob"}
    assert {i["owner_email"] for i in items} == {"alice@example.com", "bob@example.com"}

    # a maintenance szerep láthatja, de nem küldhet vissza
    maint = admin_headers(role="maintenance")
    assert client.get("/admin/storybook-submissions/pending-count", headers=maint).status_code == 200
    assert client.post(f"/admin/storybook-submissions/{a['id']}/return", json={}, headers=maint).status_code == 403

    # visszaküldés megjegyzéssel
    r = client.post(f"/admin/storybook-submissions/{a['id']}/return", json={"note": "Javítsd a 2. oldalt"}, headers=adm)
    assert r.status_code == 200 and r.json() == {"pending": 1}
    mine = client.get(f"/my/storybooks/{a['id']}", headers=alice).json()
    assert mine["submission_status"] == "draft" and mine["can_edit"] is True
    assert mine["admin_note"] == "Javítsd a 2. oldalt"

    # publikálás után kikerül a függőkből
    client.patch(f"/admin/storybooks/{b['id']}", json={"is_published": True}, headers=adm)
    assert client.get("/admin/storybook-submissions/pending-count", headers=adm).json() == {"pending": 0}
    published = client.get("/admin/storybook-submissions?state=published", headers=adm).json()
    assert [i["book_id"] for i in published] == [b["id"]]


def test_admin_endpoints_work_when_flag_is_off(client: TestClient, alice: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    b = _create(client, alice)
    _page(client, alice, b["id"])
    _submit(client, alice, b["id"])
    monkeypatch.delenv("USER_STORYBOOKS_ENABLED", raising=False)
    adm = admin_headers()
    assert client.get("/admin/storybook-submissions/pending-count", headers=adm).json() == {"pending": 1}
    assert client.get("/my/storybooks", headers=alice).status_code == 404
    assert client.patch(f"/admin/storybooks/{b['id']}", json={"is_published": True}, headers=adm).status_code == 200


def test_admin_can_edit_submitted_book_before_publishing(client: TestClient, alice: dict) -> None:
    b = _create(client, alice)
    p = _page(client, alice, b["id"])["pages"][0]
    _submit(client, alice, b["id"])
    r = client.patch(
        f"/admin/storybooks/{b['id']}/pages/{p['id']}", json={"body_text": "Admin javította"}, headers=admin_headers()
    )
    assert r.status_code == 200
    assert r.json()["pages"][0]["body_text"] == "Admin javította"


# ------------------------------------------------------------ /meseiro oldal


def test_meseiro_page_flag_and_injection(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    r = client.get("/meseiro")
    assert r.status_code == 200
    assert '<script src="/meseiro.js"></script>' in r.text and '/meseiro.css' in r.text
    # a shim az auth.js UTÁN, a fő script ELŐTT töltődik
    assert r.text.index('src="/auth.js"') < r.text.index('src="/meseiro.js"') < r.text.index("MesencsiAdminAuth;")
    assert "noindex" in r.headers.get("x-robots-tag", "")
    monkeypatch.delenv("USER_STORYBOOKS_ENABLED", raising=False)
    assert client.get("/meseiro").status_code == 404
