"""Checkout shipping methods — active providers and automatic GLS package tiers from cart quantity (Foxpost intentionally excluded)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status

from shipping_address import ShippingAddressValidationError, parse_and_validate_shipping_address_raw

# Active method ids (public checkout + admin).
PERSONAL_PICKUP = "personal_pickup"
GLS_HOME = "gls_home"

# Reserved for future use — rejected if submitted before partnership is confirmed.
FOXPOST_LOCKER = "foxpost_locker"

# GLS package tiers — computed from shippable item count; prices are fixed server-side.
GLS_TIER_SMALL = "gls_small"
GLS_TIER_MEDIUM = "gls_medium"
GLS_TIER_LARGE = "gls_large"

GLS_TIER_IDS: frozenset[str] = frozenset({GLS_TIER_SMALL, GLS_TIER_MEDIUM, GLS_TIER_LARGE})

GLS_PRICE_SMALL = 2190
GLS_PRICE_MEDIUM = 2790
GLS_PRICE_LARGE = 3290

GLS_TIER_LABELS_HU: dict[str, str] = {
    GLS_TIER_SMALL: "Kis csomag",
    GLS_TIER_MEDIUM: "Közepes csomag",
    GLS_TIER_LARGE: "Nagy csomag",
}

GLS_TIER_PRICES_HUF: dict[str, int] = {
    GLS_TIER_SMALL: GLS_PRICE_SMALL,
    GLS_TIER_MEDIUM: GLS_PRICE_MEDIUM,
    GLS_TIER_LARGE: GLS_PRICE_LARGE,
}

# Server-computed metadata — never trust client values for these keys.
_GLS_SERVER_METADATA_KEYS = frozenset(
    {
        "gls_package_tier",
        "gls_package_label_hu",
        "shippable_item_count",
        "gls_price_huf",
        "shipping_price",
        "gls_recommended_tier",
        "gls_recommended_label_hu",
    }
)

_ACTIVE_METHODS: dict[str, dict[str, object]] = {
    PERSONAL_PICKUP: {
        "label_hu": "Személyes átvétel",
        "requires_address": False,
        "price_huf": 0,
    },
    GLS_HOME: {
        "label_hu": "GLS házhozszállítás",
        "requires_address": True,
        "price_huf": None,
    },
}

_BLOCKED_METHODS: frozenset[str] = frozenset(
    {
        FOXPOST_LOCKER,
        "foxpost",
        "foxpost_locker",
        "foxpost_parcel_locker",
    }
)


def count_shippable_item_quantity(items: list[Any]) -> int:
    """Sum line quantities — all checkout cart lines are physical/shippable."""
    total = 0
    for item in items or []:
        qty = getattr(item, "quantity", None)
        if qty is None and isinstance(item, dict):
            qty = item.get("quantity")
        try:
            total += max(0, int(qty or 0))
        except (TypeError, ValueError):
            continue
    return total


def recommend_gls_shipping(shippable_item_count: int) -> tuple[str, int, str]:
    """
    GLS tier and price from cart item count (server source of truth).
    Returns (tier_id, price_huf, label_hu).
    """
    count = max(0, int(shippable_item_count))
    if count <= 3:
        return GLS_TIER_SMALL, GLS_PRICE_SMALL, GLS_TIER_LABELS_HU[GLS_TIER_SMALL]
    if count <= 6:
        return GLS_TIER_MEDIUM, GLS_PRICE_MEDIUM, GLS_TIER_LABELS_HU[GLS_TIER_MEDIUM]
    return GLS_TIER_LARGE, GLS_PRICE_LARGE, GLS_TIER_LABELS_HU[GLS_TIER_LARGE]


calculate_gls_shipping = recommend_gls_shipping


def normalize_gls_package_tier(raw: str | None) -> str:
    tier = (raw or "").strip().lower()
    if tier not in GLS_TIER_IDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Válassz GLS csomagméretet.",
        )
    return tier


def gls_price_and_label_for_tier(tier: str) -> tuple[int, str]:
    normalized = normalize_gls_package_tier(tier)
    return GLS_TIER_PRICES_HUF[normalized], GLS_TIER_LABELS_HU[normalized]


def parse_client_gls_package_tier(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    raw = metadata.get("gls_package_tier")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    return normalize_gls_package_tier(str(raw))


def build_gls_shipping_metadata(
    *,
    shippable_item_count: int,
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tier, price, label = recommend_gls_shipping(shippable_item_count)
    out = dict(base or {})
    out.update(
        {
            "gls_package_tier": tier,
            "gls_package_label_hu": label,
            "shippable_item_count": shippable_item_count,
            "gls_price_huf": price,
        }
    )
    return out


def sanitize_client_shipping_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return None
    cleaned = {k: v for k, v in metadata.items() if k not in _GLS_SERVER_METADATA_KEYS}
    return cleaned or None


def gls_package_label_from_metadata(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    label = metadata.get("gls_package_label_hu")
    if label is None:
        return None
    text = str(label).strip()
    return text or None


def resolve_shipping_price_huf(
    method: str,
    *,
    shippable_item_count: int = 0,
    gls_package_tier: str | None = None,
) -> int:
    meta = _ACTIVE_METHODS.get(method)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Érvénytelen szállítási mód.",
        )
    if method == GLS_HOME:
        if gls_package_tier:
            price, _label = gls_price_and_label_for_tier(gls_package_tier)
            return price
        _tier, price, _label = recommend_gls_shipping(shippable_item_count)
        return price
    return int(meta["price_huf"] or 0)


def shipping_method_label_hu(method: str) -> str:
    meta = _ACTIVE_METHODS.get(method)
    if meta is None:
        return method
    return str(meta["label_hu"])


def shipping_method_requires_address(method: str) -> bool:
    meta = _ACTIVE_METHODS.get(method)
    if meta is None:
        return True
    return bool(meta["requires_address"])


def normalize_shipping_method(raw: str | None) -> str:
    method = (raw or "").strip().lower()
    if not method:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Válassz szállítási módot.",
        )
    if method in _BLOCKED_METHODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A Foxpost csomagautomata szállítás jelenleg nem elérhető.",
        )
    if method not in _ACTIVE_METHODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Érvénytelen szállítási mód.",
        )
    return method


def public_gls_package_options() -> list[dict[str, object]]:
    return [
        {
            "id": GLS_TIER_SMALL,
            "label": GLS_TIER_LABELS_HU[GLS_TIER_SMALL],
            "price_huf": GLS_PRICE_SMALL,
        },
        {
            "id": GLS_TIER_MEDIUM,
            "label": GLS_TIER_LABELS_HU[GLS_TIER_MEDIUM],
            "price_huf": GLS_PRICE_MEDIUM,
        },
        {
            "id": GLS_TIER_LARGE,
            "label": GLS_TIER_LABELS_HU[GLS_TIER_LARGE],
            "price_huf": GLS_PRICE_LARGE,
        },
    ]


def public_shipping_method_options() -> list[dict[str, object]]:
    """Options exposed on GET /shop/config — never includes Foxpost."""
    out: list[dict[str, object]] = []
    for method_id, meta in _ACTIVE_METHODS.items():
        if method_id == GLS_HOME:
            out.append(
                {
                    "id": method_id,
                    "label": str(meta["label_hu"]),
                    "price_huf": None,
                    "price_from_huf": GLS_PRICE_SMALL,
                    "requires_address": bool(meta["requires_address"]),
                }
            )
        else:
            out.append(
                {
                    "id": method_id,
                    "label": str(meta["label_hu"]),
                    "price_huf": int(meta["price_huf"] or 0),
                    "price_from_huf": None,
                    "requires_address": bool(meta["requires_address"]),
                }
            )
    return out


def resolve_order_shipping(
    *,
    method_raw: str | None,
    shipping_address_raw: str | None,
    shipping_metadata: dict[str, Any] | None = None,
    shippable_item_count: int = 0,
    customer_name: str | None = None,
) -> tuple[str, int, str | None, dict[str, Any] | None]:
    """
    Validate checkout shipping choice.
    Returns (method_id, price_huf, normalized_address_or_none, metadata_or_none).
    """
    method = normalize_shipping_method(method_raw)

    price = resolve_shipping_price_huf(
        method,
        shippable_item_count=shippable_item_count,
    )
    metadata = sanitize_client_shipping_metadata(shipping_metadata)
    if metadata is not None and not isinstance(metadata, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Érvénytelen szállítási metaadat.",
        )
    if method == FOXPOST_LOCKER or (metadata and metadata.get("provider") == "foxpost"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A Foxpost csomagautomata szállítás jelenleg nem elérhető.",
        )

    if method == GLS_HOME:
        metadata = build_gls_shipping_metadata(
            shippable_item_count=shippable_item_count,
            base=metadata,
        )

    if shipping_method_requires_address(method):
        try:
            normalized = parse_and_validate_shipping_address_raw(
                shipping_address_raw,
                required=True,
                customer_name=customer_name,
            )
        except ShippingAddressValidationError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A szállítási cím megadása kötelező a GLS házhozszállításhoz.",
            )
        return method, price, normalized, metadata

    if shipping_address_raw and str(shipping_address_raw).strip():
        pass
    return method, price, None, metadata


def checkout_group_shipping_price_huf(rows: list) -> int:
    if not rows:
        return 0
    return max(int(getattr(r, "shipping_price", 0) or 0) for r in rows)


def checkout_group_products_total_huf(rows: list) -> int:
    return sum(int(r.total_price) for r in rows)


def checkout_group_grand_total_huf(rows: list) -> int:
    return checkout_group_products_total_huf(rows) + checkout_group_shipping_price_huf(rows)


def serialize_shipping_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    if not metadata:
        return None
    return metadata


def parse_shipping_metadata_field(raw: object) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Érvénytelen szállítási metaadat.",
            ) from exc
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Érvénytelen szállítási metaadat.",
            )
        return parsed
    return None
