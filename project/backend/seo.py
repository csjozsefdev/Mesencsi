"""Szerver oldali SEO: route-onkénti meta/OG/canonical, JSON-LD, robots.txt, sitemap.xml, termékoldalak.

A storefront egyetlen SPA-héj (``mesencsi.html``); a keresők és a közösségi megosztók az első
HTML-t látják, ezért a címet, leírást és a termékadatokat itt, szerver oldalon szúrjuk be.
"""

from __future__ import annotations

import html
import json
import os
import pathlib
import re
import unicodedata
from dataclasses import dataclass

from fastapi import HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from db_models import Product as ProductRow

try:
    from barion_pixel import inject_barion_pixel
except ImportError:  # régebbi telepítés: csak a statikus pixel-betöltő van az oldalban

    def inject_barion_pixel(html: str) -> str:
        return html


try:
    from email_outbound import public_base_url
except ImportError:  # régebbi telepítés

    def public_base_url() -> str:
        configured = os.environ.get("PUBLIC_SITE_URL") or os.environ.get("FRONTEND_BASE_URL")
        return (configured or "https://www.mesencsi.hu").rstrip("/")

_FRONTEND = pathlib.Path(__file__).resolve().parent.parent / "frontend"

SITE_NAME = "Mesencsi"
DEFAULT_OG_IMAGE_PATH = "/apple-touch-icon.png"
PRODUCT_VIEW_SLOT = "<!-- SEO_PRODUCT_VIEW_SLOT -->"
ORG_DESCRIPTION = (
    "A Mesencsi mesevilág webshopja: mesekönyv és kavicskészlet gyerekeknek — "
    "olvasmány, amely közös élménnyé válik az egész családnak."
)


@dataclass(frozen=True)
class RouteMeta:
    title: str
    description: str


# Útvonal → egyedi cím és leírás (a jogi oldalak is indexelhetők, de egyedi címmel).
ROUTE_META: dict[str, RouteMeta] = {
    "/": RouteMeta(
        "Mesencsi — mesevilág webshop | A kavicsok titkai mesekönyv",
        "Mesencsi mesevilág: Egy iskola, ahol bármi megtörténhet – A kavicsok titkai mesekönyv és "
        "kavicskészlet. Mese, amely közös élménnyé válik az egész családnak.",
    ),
    "/aszf": RouteMeta(
        "Általános Szerződési Feltételek — Mesencsi",
        "A Mesencsi webshop általános szerződési feltételei: megrendelés, fizetés, szállítás, elállás.",
    ),
    "/adatkezeles": RouteMeta(
        "Adatkezelési szabályzat — Mesencsi",
        "A Mesencsi webshop adatkezelési szabályzata: milyen személyes adatokat, milyen célból és "
        "meddig kezelünk, és milyen jogaid vannak.",
    ),
    "/impresszum": RouteMeta(
        "Impresszum — Mesencsi",
        "A Mesencsi webshop üzemeltetőjének adatai és elérhetőségei.",
    ),
    "/elallas": RouteMeta(
        "Elállási tájékoztató — Mesencsi",
        "Tájékoztató a Mesencsi webshopban vásárolt termékek elállási és felmondási jogáról.",
    ),
    "/szallitas": RouteMeta(
        "Szállítási tájékoztató — Mesencsi",
        "A Mesencsi webshop szállítási módjai, határidői és díjai: személyes átvétel és GLS házhozszállítás.",
    ),
    "/fizetes": RouteMeta(
        "Fizetési tájékoztató — Mesencsi",
        "Fizetési lehetőségek a Mesencsi webshopban: biztonságos bankkártyás fizetés a Barion rendszerén keresztül.",
    ),
    "/panaszkezeles": RouteMeta(
        "Panaszkezelés — Mesencsi",
        "Panaszkezelési tájékoztató és a békéltető testületi elérhetőségek a Mesencsi webshopban.",
    ),
    "/sutik": RouteMeta(
        "Süti tájékoztató — Mesencsi",
        "A Mesencsi weboldal által használt sütik és böngészőtárolás ismertetése.",
    ),
}

LEGAL_PATHS: tuple[str, ...] = tuple(p for p in ROUTE_META if p != "/")


class HeadAsGetMiddleware:
    """HEAD → GET (a törzs eldobásával).

    A storefront-útvonalak csak GET-re vannak regisztrálva, ezért a HEAD kérések (crawlerek,
    linkellenőrzők, monitorok) 404-et kaptak. Tiszta ASGI middleware: a válasz fejlécei változatlanok
    maradnak (pl. Content-Length), a törzs üres.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http" or scope.get("method") != "HEAD":
            await self.app(scope, receive, send)
            return
        scope = dict(scope)
        scope["method"] = "GET"
        body_closed = False

        async def send_without_body(message) -> None:
            nonlocal body_closed
            if message["type"] == "http.response.body":
                if body_closed:
                    return
                body_closed = True
                message = {"type": "http.response.body", "body": b"", "more_body": False}
            await send(message)

        await self.app(scope, receive, send_without_body)


# ---------------------------------------------------------------------------
# Segédfüggvények
# ---------------------------------------------------------------------------


def slugify(text: str, *, max_len: int = 60) -> str:
    """ASCII-slug magyar ékezetekkel (ő/ű is): "Kavicskészlet" → "kavicskeszlet"."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:max_len].strip("-")


def product_path(product_id: int, name: str) -> str:
    slug = slugify(name)
    return f"/termek/{product_id}-{slug}" if slug else f"/termek/{product_id}"


def _abs(base: str, path_or_url: str | None) -> str | None:
    if not path_or_url:
        return None
    value = path_or_url.strip()
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("/"):
        return base + value
    return None


def _trim(text: str, limit: int = 160) -> str:
    flat = re.sub(r"\s+", " ", text or "").strip()
    if len(flat) <= limit:
        return flat
    cut = flat[: limit - 1].rsplit(" ", 1)[0].rstrip(",.;:–-")
    return cut + "…"


def _json_ld(data: object) -> str:
    # "</" a <script> lezárását okozhatná → escape-eljük.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>'


def _head_block(
    *,
    base: str,
    path: str,
    title: str,
    description: str,
    og_type: str = "website",
    image: str | None = None,
    robots: str | None = None,
    json_ld: list[object] | None = None,
) -> str:
    canonical = base + path if path != "/" else base + "/"
    e = html.escape
    lines = [
        f'<meta name="description" content="{e(description, quote=True)}" />',
        f'<link rel="canonical" href="{e(canonical, quote=True)}" />',
        f'<meta property="og:site_name" content="{SITE_NAME}" />',
        '<meta property="og:locale" content="hu_HU" />',
        f'<meta property="og:type" content="{og_type}" />',
        f'<meta property="og:title" content="{e(title, quote=True)}" />',
        f'<meta property="og:description" content="{e(description, quote=True)}" />',
        f'<meta property="og:url" content="{e(canonical, quote=True)}" />',
    ]
    img = image or (base + DEFAULT_OG_IMAGE_PATH)
    lines.append(f'<meta property="og:image" content="{e(img, quote=True)}" />')
    lines.append(f'<meta name="twitter:card" content="{"summary_large_image" if image else "summary"}" />')
    lines.append(f'<meta name="twitter:title" content="{e(title, quote=True)}" />')
    lines.append(f'<meta name="twitter:description" content="{e(description, quote=True)}" />')
    lines.append(f'<meta name="twitter:image" content="{e(img, quote=True)}" />')
    if robots:
        lines.append(f'<meta name="robots" content="{robots}" />')
    for block in json_ld or []:
        lines.append(_json_ld(block))
    return "\n    ".join(lines)


_TITLE_RE = re.compile(r"<title>.*?</title>", re.S)


def _apply_head(page: str, *, title: str, head_block: str) -> str:
    replacement = f"<title>{html.escape(title)}</title>\n    {head_block}"
    if _TITLE_RE.search(page):
        return _TITLE_RE.sub(lambda _m: replacement, page, count=1)
    return page.replace("</head>", f"    {head_block}\n  </head>", 1)


def _organization_graph(base: str) -> list[object]:
    org: dict[str, object] = {
        "@type": "Organization",
        "@id": base + "/#organization",
        "name": SITE_NAME,
        "url": base + "/",
        "logo": base + DEFAULT_OG_IMAGE_PATH,
        "description": ORG_DESCRIPTION,
    }
    site = {
        "@type": "WebSite",
        "@id": base + "/#website",
        "url": base + "/",
        "name": SITE_NAME,
        "inLanguage": "hu-HU",
        "publisher": {"@id": base + "/#organization"},
    }
    return [{"@context": "https://schema.org", "@graph": [org, site]}]


# ---------------------------------------------------------------------------
# Termékoldal
# ---------------------------------------------------------------------------


def _product_view_html(product: ProductRow, base: str) -> str:
    e = lambda s: html.escape(str(s), quote=True)  # noqa: E731
    desc = (product.description or "").strip()
    paragraphs = "".join(f"<p>{e(p)}</p>" for p in re.split(r"\n\s*\n", desc) if p.strip()) if desc else ""
    # egyetlen sortörés a bekezdésen belül is megjelenjen
    paragraphs = paragraphs.replace("\n", "<br />")
    img = ""
    if product.image_url and product.image_url.strip().startswith("/"):
        img = (
            f'<div class="product-detail__image"><img src="{e(product.image_url.strip())}" '
            f'alt="{e(product.name)}" decoding="async" /></div>'
        )
    price = f"{int(product.price):,}".replace(",", " ") + " Ft"
    return (
        '<section id="view-product" class="view" hidden data-testid="view-product" '
        f'data-product-id="{int(product.id)}">\n'
        '  <div class="glass-card view-inner product-detail">\n'
        '    <button type="button" class="btn-back" data-route="/">← Vissza a főoldalra</button>\n'
        f"    {img}\n"
        f"    <h1>{e(product.name)}</h1>\n"
        f'    <p class="price product-detail__price">{e(price)}</p>\n'
        f'    <div class="product-detail__desc">{paragraphs}</div>\n'
        '    <p class="product-detail__note">A kosárba tétel és a rendelés bejelentkezés után, a '
        "<strong>Webshop</strong> menüben érhető el. A szállítás díjáról a "
        '<a href="/szallitas" data-route="/szallitas">Szállítási tájékoztatóban</a> olvashatsz.</p>\n'
        "  </div>\n"
        "</section>"
    )


def _product_json_ld(product: ProductRow, base: str, canonical_path: str) -> dict[str, object]:
    data: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "url": base + canonical_path,
        "brand": {"@type": "Brand", "name": SITE_NAME},
        "offers": {
            "@type": "Offer",
            "url": base + canonical_path,
            "price": str(int(product.price)),
            "priceCurrency": "HUF",
        },
    }
    desc = (product.description or "").strip()
    if desc:
        data["description"] = re.sub(r"\s+", " ", desc)
    image = _abs(base, product.image_url)
    if image:
        data["image"] = [image]
    return data


def parse_product_ref(ref: str) -> int | None:
    m = re.match(r"^(\d{1,9})(?:-.*)?$", ref or "")
    return int(m.group(1)) if m else None


def serve_product_page(product_ref: str, db: Session) -> Response:
    product_id = parse_product_ref(product_ref)
    if product_id is None:
        raise HTTPException(status_code=404, detail="A termék nem található.")
    product = db.get(ProductRow, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="A termék nem található.")
    canonical_path = product_path(product.id, product.name)
    if "/termek/" + product_ref != canonical_path:
        return RedirectResponse(canonical_path, status_code=301)

    base = public_base_url()
    path = _FRONTEND / "mesencsi.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Az oldal nem található.")
    page = path.read_text(encoding="utf-8")

    title = f"{product.name} — {SITE_NAME}"
    description = _trim(
        (product.description or "").strip() or f"{product.name} a Mesencsi webshopban.", 160
    )
    head = _head_block(
        base=base,
        path=canonical_path,
        title=title,
        description=description,
        og_type="product",
        image=_abs(base, product.image_url),
        json_ld=[_product_json_ld(product, base, canonical_path)],
    )
    page = _apply_head(page, title=title, head_block=head)
    if PRODUCT_VIEW_SLOT in page:
        page = page.replace(PRODUCT_VIEW_SLOT, _product_view_html(product, base))
    return HTMLResponse(inject_barion_pixel(page))


# ---------------------------------------------------------------------------
# Útvonalak: főoldal/jogi oldalak, robots.txt, sitemap.xml
# ---------------------------------------------------------------------------


def serve_storefront_with_meta(path: str) -> Response:
    """A SPA-héj az adott útvonal egyedi head-adataival."""
    meta = ROUTE_META.get(path)
    file = _FRONTEND / "mesencsi.html"
    if not file.is_file():
        raise HTTPException(status_code=404, detail="Az oldal nem található.")
    page = file.read_text(encoding="utf-8")
    if meta is not None:
        base = public_base_url()
        head = _head_block(
            base=base,
            path=path,
            title=meta.title,
            description=meta.description,
            json_ld=_organization_graph(base) if path == "/" else None,
        )
        page = _apply_head(page, title=meta.title, head_block=head)
    # A termékoldal szekciója csak a /termek/… útvonalon létezik.
    page = page.replace(PRODUCT_VIEW_SLOT, "")
    return HTMLResponse(inject_barion_pixel(page))


ROBOTS_DISALLOW: tuple[str, ...] = (
    "/admin",
    "/auth/",
    "/cart",
    "/orders",
    "/payments/",
    "/users/",
    "/internal/",
    "/dev/",
    "/forgot-password.html",
    "/reset-password.html",
)


def robots_txt() -> PlainTextResponse:
    base = public_base_url()
    lines = ["User-agent: *"]
    lines += [f"Disallow: {p}" for p in ROBOTS_DISALLOW]
    lines += ["Allow: /", "", f"Sitemap: {base}/sitemap.xml", ""]
    return PlainTextResponse("\n".join(lines))


def sitemap_xml(db: Session) -> Response:
    base = public_base_url()
    urls: list[str] = [base + "/"] + [base + p for p in LEGAL_PATHS]
    for row in db.scalars(select(ProductRow).order_by(ProductRow.id)).all():
        urls.append(base + product_path(row.id, row.name))
    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        body.append(f"  <url><loc>{html.escape(u)}</loc></url>")
    body.append("</urlset>")
    return Response("\n".join(body) + "\n", media_type="application/xml")
