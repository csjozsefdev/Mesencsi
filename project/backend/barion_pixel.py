"""Barion Base Pixel markup for public storefront HTML pages.

The pixel ID is read from ``BARION_PIXEL_ID`` at response time only — never logged.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import HTMLResponse

_PIXEL_ID_RE = re.compile(r"^BP-[A-Za-z0-9]{10}-[0-9]{2}$")
_BARION_PIXEL_SLOT = "<!-- BARION_PIXEL_SLOT -->"
_BACKEND = Path(__file__).resolve().parent
_FRONTEND = _BACKEND.parent / "frontend"


def barion_pixel_id() -> str | None:
    """Return validated Barion Pixel ID from env, or None if unset/invalid."""
    raw = (os.environ.get("BARION_PIXEL_ID") or "").strip()
    if not raw or not _PIXEL_ID_RE.match(raw):
        return None
    return raw


def barion_pixel_markup(pixel_id: str) -> str:
    """Inline Base Pixel snippet (const/let loader + noscript fallback)."""
    return f"""<!-- Barion Base Pixel - required for Barion merchant approval -->
<script>
    window["bp"] = window["bp"] || function () {{
        (window["bp"].q = window["bp"].q || []).push(arguments);
    }};
    window["bp"].l = 1 * new Date();

    const scriptElement = document.createElement("script");
    const firstScript = document.getElementsByTagName("script")[0];

    scriptElement.async = true;
    scriptElement.src = "https://pixel.barion.com/bp.js";
    firstScript.parentNode.insertBefore(scriptElement, firstScript);

    window['barion_pixel_id'] = '{pixel_id}';

    bp('init', 'addBarionPixelId', window['barion_pixel_id']);
</script>
<noscript>
    <img height="1" width="1" style="display:none" alt="Barion Pixel"
         src="https://pixel.barion.com/a.gif?ba_pixel_id={pixel_id}&ev=contentView&noscript=1">
</noscript>"""


def inject_barion_pixel(html: str) -> str:
    """Replace ``<!-- BARION_PIXEL_SLOT -->`` with pixel markup or remove the slot."""
    pixel_id = barion_pixel_id()
    if pixel_id is None:
        return html.replace(_BARION_PIXEL_SLOT, "")
    markup = barion_pixel_markup(pixel_id)
    if _BARION_PIXEL_SLOT in html:
        return html.replace(_BARION_PIXEL_SLOT, markup)
    return html.replace("</head>", f"{markup}\n  </head>", 1)


def serve_public_html(filename: str) -> HTMLResponse:
    """Serve a public frontend HTML file with optional Barion pixel injection."""
    path = _FRONTEND / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Az oldal nem található.")
    html = path.read_text(encoding="utf-8")
    return HTMLResponse(inject_barion_pixel(html))
