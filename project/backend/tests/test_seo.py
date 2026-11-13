from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import Product as ProductRow
from mesencsi import app
from seo import ROUTE_META, parse_product_ref, product_path, slugify


def _seed_product(name: str = "Kavicskészlet", description: str = "Nem minden kincs csillog.\n\nKözös kaland.") -> ProductRow:
    with SessionLocal() as db:
        row = ProductRow(name=name, price=2990, description=description, image_url="/media/uploads/products/x.jpg")
        db.add(row)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row


def _ld_blocks(page: str) -> list[dict]:
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)]


def test_slugify_handles_hungarian_accents() -> None:
    assert slugify("Kavicskészlet") == "kavicskeszlet"
    assert slugify("Egy iskola, ahol bármi megtörténhet- A kavicsok titkai könyv").startswith("egy-iskola-ahol-barmi-megtortenhet-a-kavicsok")
    assert slugify("Őszi Fűzfa") == "oszi-fuzfa"
    assert slugify("???") == ""
    assert product_path(7, "???") == "/termek/7"
    assert parse_product_ref("5-egy-iskola") == 5
    assert parse_product_ref("abc") is None


def test_every_route_has_unique_title_description_and_canonical() -> None:
    titles = set()
    with TestClient(app) as client:
        for path, meta in ROUTE_META.items():
            response = client.get(path)
            assert response.status_code == 200, path
            page = response.text
            assert f"<title>{meta.title}</title>" in page or "&amp;" in page, path
            assert '<meta name="description"' in page, path
            assert re.search(r'<link rel="canonical" href="[^"]+' + (re.escape(path) if path != "/" else "/") + '"', page), path
            assert 'property="og:title"' in page and 'name="twitter:card"' in page, path
            assert page.count("<title>") == 1, path
            titles.add(meta.title)
    assert len(titles) == len(ROUTE_META)


def test_home_has_organization_json_ld_and_single_h1() -> None:
    with TestClient(app) as client:
        page = client.get("/").text
    graph = _ld_blocks(page)[0]["@graph"]
    assert {n["@type"] for n in graph} == {"Organization", "WebSite"}
    assert page.count("<h1") == 1
    assert "SEO_PRODUCT_VIEW_SLOT" not in page


def test_product_page_renders_server_side_with_product_json_ld() -> None:
    row = _seed_product()
    path = product_path(row.id, row.name)
    with TestClient(app) as client:
        response = client.get(path)
        assert response.status_code == 200
        page = response.text
        assert f"<title>Kavicskészlet — Mesencsi</title>" in page
        assert f'<link rel="canonical" href="' in page and path in page
        assert 'id="view-product"' in page and "<h1>Kavicskészlet</h1>" in page
        assert "Nem minden kincs csillog." in page
        product_ld = [b for b in _ld_blocks(page) if b.get("@type") == "Product"][0]
        assert product_ld["name"] == "Kavicskészlet"
        assert product_ld["offers"]["price"] == "2990" and product_ld["offers"]["priceCurrency"] == "HUF"
        assert product_ld["image"][0].endswith("/media/uploads/products/x.jpg")
        # nem kanonikus slug / csak id → 301 a kanonikusra
        for variant in (f"/termek/{row.id}", f"/termek/{row.id}-rossz-slug"):
            redirect = client.get(variant, follow_redirects=False)
            assert redirect.status_code == 301, variant
            assert redirect.headers["location"] == path
        assert client.get("/termek/999999").status_code == 404
        assert client.get("/termek/nincs").status_code == 404


def test_robots_and_sitemap() -> None:
    row = _seed_product("Sitemap termék")
    with TestClient(app) as client:
        robots = client.get("/robots.txt")
        assert robots.status_code == 200 and robots.headers["content-type"].startswith("text/plain")
        assert "Disallow: /admin" in robots.text and "Sitemap: " in robots.text and robots.text.rstrip().endswith("/sitemap.xml")
        sitemap = client.get("/sitemap.xml")
        assert sitemap.status_code == 200 and "xml" in sitemap.headers["content-type"]
        locs = re.findall(r"<loc>(.*?)</loc>", sitemap.text)
        assert any(u.endswith("/szallitas") for u in locs)
        assert any(u.endswith(product_path(row.id, row.name)) for u in locs)
        assert len(locs) == len(set(locs))


def test_admin_and_password_pages_are_noindex() -> None:
    with TestClient(app) as client:
        for path in ("/admin/login", "/forgot-password.html"):
            response = client.get(path)
            if response.status_code == 200:
                assert "noindex" in response.headers.get("x-robots-tag", ""), path


def test_head_requests_work_like_get_without_body() -> None:
    row = _seed_product("Head termék")
    with TestClient(app) as client:
        for path in ("/", "/szallitas", "/robots.txt", "/sitemap.xml", product_path(row.id, row.name), "/style.css"):
            get = client.get(path)
            head = client.head(path)
            assert head.status_code == get.status_code == 200, path
            assert head.content == b"", path
            assert head.headers["content-type"] == get.headers["content-type"], path
        assert client.head("/termek/999999").status_code == 404
        assert client.head(f"/termek/{row.id}", follow_redirects=False).status_code == 301
