"""Profile image URL allowlist — local uploads only."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from image_upload import (
    AVATAR_PRESET_PREFIX,
    AVATAR_UPLOAD_PREFIX,
    validate_profile_image_url,
)
from mesencsi import app
from tests.test_checkout_bundle_integration import _auth_headers, _seed_verified_user_and_products


def test_validate_profile_image_url_accepts_avatar_upload_path() -> None:
    url = AVATAR_UPLOAD_PREFIX + "user-1-abc123.jpg"
    assert validate_profile_image_url(url) == url


def test_validate_profile_image_url_accepts_builtin_presets() -> None:
    for n in range(1, 5):
        url = f"{AVATAR_PRESET_PREFIX}preset-{n}.svg"
        assert validate_profile_image_url(url) == url


def test_validate_profile_image_url_rejects_external_and_traversal() -> None:
    with pytest.raises(ValueError, match="Külső"):
        validate_profile_image_url("https://evil.example/x.jpg")
    with pytest.raises(ValueError):
        validate_profile_image_url("/media/uploads/avatars/../gallery/x.jpg")
    with pytest.raises(ValueError, match="profilkép"):
        validate_profile_image_url("/media/uploads/gallery/x.jpg")


@pytest.mark.parametrize(
    "bad_url",
    [
        "javascript:alert(1)",
        "data:image/svg+xml,<svg onload=alert(1)>",
        "//evil.example/avatar.jpg",
        "https://evil.example/x.jpg",
        "http://evil.example/x.jpg",
    ],
)
def test_validate_profile_image_url_rejects_dangerous_schemes(bad_url: str) -> None:
    with pytest.raises(ValueError):
        validate_profile_image_url(bad_url)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize(
    "bad_url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "//cdn.evil/avatar.png",
    ],
)
def test_patch_profile_rejects_unsafe_profile_image_url(
    client: TestClient, bad_url: str
) -> None:
    uid, _pa, _pb = _seed_verified_user_and_products()
    r = client.patch(
        "/users/me",
        json={"profile_image_url": bad_url},
        headers=_auth_headers(uid),
    )
    assert r.status_code == 422, r.text


def test_patch_profile_accepts_valid_avatar_path(client: TestClient) -> None:
    uid, _pa, _pb = _seed_verified_user_and_products()
    url = AVATAR_UPLOAD_PREFIX + "user-99-test.jpg"
    r = client.patch(
        "/users/me",
        json={"profile_image_url": url},
        headers=_auth_headers(uid),
    )
    assert r.status_code == 200, r.text
    assert r.json()["profile_image_url"] == url


def test_patch_profile_accepts_preset_avatar(client: TestClient) -> None:
    uid, _pa, _pb = _seed_verified_user_and_products()
    url = f"{AVATAR_PRESET_PREFIX}preset-2.svg"
    r = client.patch(
        "/users/me",
        json={"profile_image_url": url},
        headers=_auth_headers(uid),
    )
    assert r.status_code == 200, r.text
    assert r.json()["profile_image_url"] == url
