"""Public shop configuration (no auth)."""

from __future__ import annotations

from fastapi import APIRouter

from models import ShopPublicConfig
from shop_config import shop_products_coming_soon, shop_products_coming_soon_message

router = APIRouter(prefix="/shop", tags=["shop"])


@router.get("/config", response_model=ShopPublicConfig)
def shop_public_config() -> ShopPublicConfig:
    return ShopPublicConfig(
        products_coming_soon=shop_products_coming_soon(),
        products_coming_soon_message=shop_products_coming_soon_message(),
    )
