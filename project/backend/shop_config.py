"""Public shop UX flags (storefront, no secrets)."""

from __future__ import annotations

import os


def _env_truthy(name: str) -> bool:
    v = (os.environ.get(name) or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def shop_products_coming_soon() -> bool:
    """When true, the storefront shows a placeholder instead of the product grid."""
    return _env_truthy("SHOP_PRODUCTS_COMING_SOON")


def shop_products_coming_soon_message() -> str | None:
    raw = (os.environ.get("SHOP_PRODUCTS_COMING_SOON_MESSAGE") or "").strip()
    return raw or None
