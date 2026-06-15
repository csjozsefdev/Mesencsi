"""Public shop configuration (no auth)."""

from __future__ import annotations

from fastapi import APIRouter

from shop_config import shop_products_coming_soon, shop_products_coming_soon_message
from models import GlsPackagePublicOption, ShippingMethodPublicOption, ShopPublicConfig
from shipping_methods import public_gls_package_options, public_shipping_method_options

router = APIRouter(prefix="/shop", tags=["shop"])


@router.get("/config", response_model=ShopPublicConfig)
def shop_public_config() -> ShopPublicConfig:
    methods = [
        ShippingMethodPublicOption.model_validate(m) for m in public_shipping_method_options()
    ]
    gls_options = [
        GlsPackagePublicOption.model_validate(o) for o in public_gls_package_options()
    ]
    return ShopPublicConfig(
        products_coming_soon=shop_products_coming_soon(),
        products_coming_soon_message=shop_products_coming_soon_message(),
        shipping_methods=methods,
        gls_package_options=gls_options,
    )
