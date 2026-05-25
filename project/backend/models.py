"""Pydantic request/response modellek — shop, admin és publikus API."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator, model_validator

from image_upload import validate_profile_image_url
from shipping_address import (
    ShippingAddressValidationError,
    contains_unsafe_markup,
    parse_and_validate_shipping_address_raw,
    validate_person_name,
)

OrderPaymentStatus = Literal["pending", "paid", "failed", "cancelled"]


class Product(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: int
    description: str
    image_url: str | None = None


class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=255)
    price: int = Field(..., ge=0)
    description: str = Field(default="", max_length=2000)


class ProductUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=255)
    price: int | None = Field(None, ge=0)
    description: str | None = Field(None, max_length=2000)


class OrderLineItem(BaseModel):
    """One line in a cart checkout request."""

    product_id: int
    quantity: int = Field(..., gt=0)


class CartLineItem(BaseModel):
    """One line in a persisted user cart."""

    product_id: int
    quantity: int = Field(..., gt=0, le=999)


class CartPutRequest(BaseModel):
    """Replace the authenticated user's cart with these lines."""

    items: list[CartLineItem] = Field(default_factory=list)


class CartLineRead(BaseModel):
    """Cart line returned to the storefront (product snapshot for UI)."""

    product_id: int
    quantity: int
    name: str
    price: int
    description: str


class Order(BaseModel):
    """Checkout body: JWT-hez kötött vásárló; az e-mail a fiókból kerül a rendelési sorokba (nem küldhető a kliensnek)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    customer_name: str = Field(..., min_length=1, max_length=255, description="Buyer / parent name.")
    items: list[OrderLineItem] = Field(..., min_length=1, description="At least one product line.")
    shipping_address: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Structured JSON shipping address (validated server-side).",
    )
    notes: str | None = Field(None, max_length=2000, description="Message to the author / shop.")
    coupon_code: str | None = Field(None, max_length=64, description="Opcionális kuponkód — a szerver számolja újra az árat.")
    # Honeypot (bot): a kliens hagyja üresen; nem kell kitölteni.
    company_website: str | None = Field(None, max_length=256, description="Honeypot — üresen hagyandó.")

    @field_validator("customer_name", mode="before")
    @classmethod
    def validate_order_customer_name(cls, v: object) -> str:
        try:
            return validate_person_name(v, field="customer_name", label="név")
        except ShippingAddressValidationError as e:
            raise ValueError(str(e)) from e

    @field_validator("shipping_address", mode="before")
    @classmethod
    def validate_order_shipping_address(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            raise ValueError("A szállítási cím megadása kötelező.")
        try:
            normalized = parse_and_validate_shipping_address_raw(str(v), required=True)
        except ShippingAddressValidationError as e:
            raise ValueError(str(e)) from e
        if not normalized:
            raise ValueError("A szállítási cím megadása kötelező.")
        return normalized

    @field_validator("notes", "coupon_code", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("notes", mode="after")
    @classmethod
    def validate_order_notes(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) > 2000:
            raise ValueError("A megjegyzés legfeljebb 2000 karakter lehet.")
        if contains_unsafe_markup(v):
            raise ValueError("A megjegyzés nem tartalmazhat HTML-t vagy szkriptet.")
        return v

    @field_validator("company_website", mode="before")
    @classmethod
    def honeypot_order(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str) and v.strip():
            raise ValueError("Érvénytelen kérés.")
        return None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    quantity: int
    total_price: int
    original_total: int | None = None
    discount_percent: int | None = None
    discount_amount: int | None = None
    coupon_code: str | None = None
    bundle_rule_id: int | None = None
    bundle_rule_name: str | None = None
    bundle_discount_amount: int | None = None
    customer_name: str
    customer_email: str | None = None
    shipping_address: str | None = None
    notes: str | None = None
    status: str
    payment_status: str
    checkout_group_id: str | None = None
    barion_payment_id: str | None = None
    placed_at: datetime

    @computed_field
    def final_total(self) -> int:
        """Fizetendő sorösszeg (Ft) — megegyezik a ``total_price`` mezővel."""
        return self.total_price


class OrderEstimateLine(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    original_total: int
    discount_amount: int
    final_total: int
    bundle_discount_amount: int | None = None


class OrderEstimateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    items: list[OrderLineItem] = Field(..., min_length=1)
    coupon_code: str | None = Field(None, max_length=64)

    @field_validator("coupon_code", mode="before")
    @classmethod
    def empty_coupon(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class OrderEstimateResponse(BaseModel):
    discount_percent: int | None = None
    coupon_code: str | None = None
    bundle_rule_name: str | None = None
    bundle_discount_total: int = 0
    bundle_percent: int | None = None
    lines: list[OrderEstimateLine]
    grand_original: int
    grand_discount: int
    grand_final: int


class ProductBundleDiscountCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=8000)
    percent_discount: int = Field(..., ge=0, le=100)
    is_active: bool = True
    product_ids: list[int] = Field(..., min_length=1, description="Legalább két különböző termék-id.")

    @field_validator("description", mode="before")
    @classmethod
    def empty_desc(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("product_ids", mode="after")
    @classmethod
    def at_least_two_distinct_products(cls, v: list[int]) -> list[int]:
        uniq = {int(x) for x in v}
        if len(uniq) < 2:
            raise ValueError("A kombó kedvezményhez legalább két különböző terméket kell választani.")
        return sorted(uniq)


class ProductBundleDiscountUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=8000)
    percent_discount: int | None = Field(None, ge=0, le=100)
    is_active: bool | None = None
    product_ids: list[int] | None = Field(
        None,
        description="Ha megadod, felülírja a kapcsolt termékeket (legalább két különböző id).",
    )

    @field_validator("description", mode="before")
    @classmethod
    def empty_desc(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("product_ids", mode="after")
    @classmethod
    def two_distinct_if_set(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        uniq = {int(x) for x in v}
        if len(uniq) < 2:
            raise ValueError("A kombó kedvezményhez legalább két különböző terméket kell választani.")
        return sorted(uniq)

    @model_validator(mode="after")
    def at_least_one(self) -> ProductBundleDiscountUpdate:
        if all(
            v is None
            for v in (self.name, self.description, self.percent_discount, self.is_active, self.product_ids)
        ):
            raise ValueError("Legalább egy mezőt meg kell adni a módosításhoz.")
        return self


class ProductBundleDiscountRead(BaseModel):
    """Admin lista / részletek — termék id-k a kapcsolótáblából."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    percent_discount: int
    is_active: bool
    product_ids: list[int]
    created_at: datetime
    updated_at: datetime


class CouponCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(..., min_length=1, max_length=64)
    percent_discount: int = Field(
        ...,
        ge=1,
        le=100,
        description="Százalékos kedvezmény (egész szám), 1–100. Példák: 5, 10, 15, 25.",
    )
    user_id: int | None = Field(None, description="Ha megadod, csak ez a user használhatja a kupont.")
    is_active: bool = True
    expires_at: datetime | None = None


class CouponUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str | None = Field(None, min_length=1, max_length=64)
    percent_discount: int | None = Field(None, ge=1, le=100)
    user_id: int | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> CouponUpdate:
        if all(
            v is None
            for v in (self.code, self.percent_discount, self.user_id, self.is_active, self.expires_at)
        ):
            raise ValueError("Legalább egy mezőt meg kell adni.")
        return self


class CouponRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    percent_discount: int
    user_id: int | None
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CouponPublicRead(BaseModel):
    """Vásárlónak listázott aktív kupon — nincs benne inaktív jelző."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    percent_discount: int
    expires_at: datetime | None


class UserDiscountAssignCreate(BaseModel):
    """Admin: személyre szabott kupon létrehozása egy userhez."""

    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(..., min_length=1, max_length=64)
    percent_discount: int = Field(
        ...,
        ge=1,
        le=100,
        description="Százalékos kedvezmény (egész szám), 1–100.",
    )
    expires_at: datetime | None = None
    is_active: bool = True


OrderAdminStatus = Literal["new", "processing", "completed", "cancelled"]


class AdminOrderStatusPatch(BaseModel):
    """Admin-only: set shop order line status (same value is kept on all lines of one checkout)."""

    status: OrderAdminStatus | None = None
    payment_status: OrderPaymentStatus | None = None

    @model_validator(mode="after")
    def at_least_one_admin_order_field(self) -> AdminOrderStatusPatch:
        if self.status is None and self.payment_status is None:
            raise ValueError("Legalább egy mezőt meg kell adni (status vagy payment_status).")
        return self


class GalleryItemRead(BaseModel):
    """One gallery image / card for the storefront gallery."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    image_url: str
    description: str | None = None
    sort_order: int
    created_at: datetime


_GALLERY_UPLOAD_PREFIX = "/media/uploads/gallery/"


class GalleryItemCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=255)
    image_url: str = Field(..., min_length=1, max_length=4000)
    description: str | None = Field(None, max_length=4000)
    sort_order: int = 0

    @field_validator("image_url")
    @classmethod
    def gallery_image_local_path(cls, v: str) -> str:
        s = (v or "").strip()
        if not s.startswith(_GALLERY_UPLOAD_PREFIX) or ".." in s:
            raise ValueError(
                "A galériaképhez csak a szerverre feltöltött helyi útvonal használható (/media/uploads/gallery/…)."
            )
        if s.lower().startswith("http://") or s.lower().startswith("https://"):
            raise ValueError("Külső kép URL nem engedélyezett.")
        return s


class GalleryItemUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=255)
    image_url: str | None = Field(None, min_length=1, max_length=4000)
    description: str | None = Field(None, max_length=4000)
    sort_order: int | None = None

    @field_validator("image_url")
    @classmethod
    def gallery_image_local_path_update(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s.startswith(_GALLERY_UPLOAD_PREFIX) or ".." in s:
            raise ValueError(
                "A galériaképhez csak a szerverre feltöltött helyi útvonal használható (/media/uploads/gallery/…)."
            )
        if s.lower().startswith("http://") or s.lower().startswith("https://"):
            raise ValueError("Külső kép URL nem engedélyezett.")
        return s


class StoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    sort_order: int
    created_at: datetime


class StoryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=50_000)
    sort_order: int = 0


class StoryUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=255)
    body: str | None = Field(None, min_length=1, max_length=50_000)
    sort_order: int | None = None


# --- News / újdonságok (publikus lista + admin CRUD) ---


class NewsCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=255)
    summary: str = Field(..., min_length=1, max_length=4000)
    body: str = Field(..., min_length=1, max_length=100_000)
    slug: str | None = Field(None, min_length=1, max_length=255)
    is_published: bool = False
    is_featured: bool = False
    release_event_at: datetime | None = None


class NewsUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=255)
    summary: str | None = Field(None, min_length=1, max_length=4000)
    body: str | None = Field(None, min_length=1, max_length=100_000)
    slug: str | None = Field(None, min_length=1, max_length=255)
    is_published: bool | None = None
    is_featured: bool | None = None
    release_event_at: datetime | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> NewsUpdate:
        if all(
            v is None
            for v in (
                self.title,
                self.summary,
                self.body,
                self.slug,
                self.is_published,
                self.is_featured,
                self.release_event_at,
            )
        ):
            raise ValueError("Legalább egy mezőt meg kell adni a módosításhoz.")
        return self


class NewsRead(BaseModel):
    """Admin: teljes rekord (vázlatok is)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    summary: str
    body: str
    image_url: str | None
    is_published: bool
    is_featured: bool
    release_event_at: datetime | None
    published_at: datetime | None
    author_username: str | None
    created_at: datetime
    updated_at: datetime


class NewsListItemPublic(BaseModel):
    """Publikus listaelem — nincs benne szerkesztői / vázlat meta."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    summary: str
    image_url: str | None
    published_at: datetime | None
    comment_count: int = 0


class NewsPublicDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    summary: str
    body: str
    image_url: str | None
    published_at: datetime | None
    comment_count: int = 0


class NewsPage(BaseModel):
    items: list[NewsListItemPublic]
    total: int
    page: int
    page_size: int
    pages: int


class NewsCommentCreate(BaseModel):
    """Bejelentkezett vásárló: új hozzászólás közzétett hírhez."""

    model_config = ConfigDict(str_strip_whitespace=True)

    content: str = Field(..., min_length=2, max_length=2000)

    @field_validator("content", mode="after")
    @classmethod
    def nonempty_comment(cls, v: str) -> str:
        s = (v or "").strip()
        if len(s) < 2:
            raise ValueError("A hozzászólás legalább 2 karakter legyen, és ne legyen csak szóköz.")
        return s


class NewsCommentPublic(BaseModel):
    """Publikus listaelem — nincs e-mail, nincs belső user id."""

    id: int
    content: str
    created_at: datetime
    author_display_name: str
    author_avatar_url: str | None = None


class NewsCommentPage(BaseModel):
    items: list[NewsCommentPublic]
    total: int
    page: int
    page_size: int
    pages: int


class AdminNewsCommentRead(BaseModel):
    """Admin moderációs lista — belső azonosítók + hír címe."""

    id: int
    news_id: int
    news_title: str
    user_id: int | None
    user_email: str | None
    content: str
    is_visible: bool
    created_at: datetime
    updated_at: datetime


class NewsCommentVisibilityPatch(BaseModel):
    is_visible: bool


class AdminNewsCommentPage(BaseModel):
    items: list[AdminNewsCommentRead]
    total: int
    page: int
    page_size: int
    pages: int


class NewsPublishUpdate(BaseModel):
    is_published: bool


class NewsFeatureUpdate(BaseModel):
    is_featured: bool


class AdminImageUploadResponse(BaseModel):
    """Public URL path served by ``GET /images/{filename}`` after owner upload."""

    url: str
    filename: str


class GalleryPage(BaseModel):
    """Paginated gallery response (page is 1-based)."""

    items: list[GalleryItemRead]
    total: int
    page: int
    page_size: int
    pages: int


class IncidentRead(BaseModel):
    """API shape for reading persisted incidents (e.g. admin tools)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    request_id: str | None
    method: str
    path: str
    status_code: int | None
    error_type: str
    message: str
    traceback: str | None


# --- Digitális storybook (admin szerkesztés; publikus csak közzétett) ---


def _animation_settings_ok(v: dict) -> dict:
    if not isinstance(v, dict):
        raise TypeError("Az animációs beállításoknak objektumnak kell lenniük.")
    raw = json.dumps(v, ensure_ascii=False)
    if len(raw) > 32000:
        raise ValueError("Az animációs beállítások túl nagyok (legfeljebb ~32 KB JSON).")
    return v


StorybookTextPosV = Literal["top", "center", "bottom"]
StorybookTextPosH = Literal["left", "center", "right"]
StorybookTextBoxStyle = Literal[
    "card",
    "rounded",
    "cloud",
    "bubble",
    "parchment",
    "letter",
    "star",
    "storyboard",
    "bookpage",
    "magic_frame",
]


class StorybookPagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_index: int
    title: str | None
    body_text: str
    image_url: str | None
    audio_url: str | None
    text_position_vertical: StorybookTextPosV = "center"
    text_position_horizontal: StorybookTextPosH = "center"
    text_box_style: StorybookTextBoxStyle = "card"
    text_x_percent: float | None = None
    text_y_percent: float | None = None


class StorybookListItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: str | None
    cover_image_url: str | None
    updated_at: datetime


class StorybookPublicDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: str | None
    cover_image_url: str | None
    animation_settings: dict
    updated_at: datetime
    pages: list[StorybookPagePublic]


class StorybookAdminPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    page_index: int
    title: str | None
    body_text: str
    image_url: str | None
    audio_url: str | None
    text_position_vertical: StorybookTextPosV = "center"
    text_position_horizontal: StorybookTextPosH = "center"
    text_box_style: StorybookTextBoxStyle = "card"
    text_x_percent: float | None = None
    text_y_percent: float | None = None
    extra: dict


class StorybookAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    description: str | None
    cover_image_url: str | None
    is_published: bool
    animation_settings: dict
    created_at: datetime
    updated_at: datetime
    pages: list[StorybookAdminPageRead]


class StorybookAdminListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    is_published: bool
    updated_at: datetime


class StorybookCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=8000)

    @field_validator("description", mode="before")
    @classmethod
    def empty_desc_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class StorybookUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=8000)
    is_published: bool | None = None
    animation_settings: dict | None = None

    @field_validator("description", mode="before")
    @classmethod
    def empty_desc_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("animation_settings")
    @classmethod
    def validate_anim(cls, v: dict | None) -> dict | None:
        if v is None:
            return None
        return _animation_settings_ok(v)


class StorybookPageCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, max_length=255)
    body_text: str = Field(default="", max_length=50000)

    @field_validator("title", mode="before")
    @classmethod
    def empty_title_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class StorybookPageUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, max_length=255)
    body_text: str | None = Field(None, max_length=50000)
    audio_url: str | None = Field(None, max_length=4000)
    text_position_vertical: StorybookTextPosV | None = None
    text_position_horizontal: StorybookTextPosH | None = None
    text_box_style: StorybookTextBoxStyle | None = None
    text_x_percent: float | None = None
    text_y_percent: float | None = None
    extra: dict | None = None

    @field_validator("text_x_percent", "text_y_percent", mode="before")
    @classmethod
    def clamp_text_percent(cls, v: object) -> object:
        if v is None:
            return None
        try:
            x = float(v)
        except (TypeError, ValueError):
            raise ValueError("A szövegpozíció százalékának számnak kell lennie.") from None
        if x < 0 or x > 100:
            raise ValueError("A szövegpozíció százaléka 0 és 100 között lehet.")
        return round(x, 4)

    @field_validator("title", "audio_url", mode="before")
    @classmethod
    def empty_str_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("extra")
    @classmethod
    def validate_extra(cls, v: dict | None) -> dict | None:
        if v is None:
            return None
        raw = json.dumps(v, ensure_ascii=False)
        if len(raw) > 16000:
            raise ValueError("Az oldal kiegészítő adatai túl nagyok.")
        return v


class StorybookPagesReorder(BaseModel):
    """Minden oldal azonosítója pontosan egyszer — új sorrend 1-től indexelve."""

    ordered_page_ids: list[int] = Field(..., min_length=1)


class AdminStorybookMediaUploadResponse(BaseModel):
    url: str
    filename: str


# --- Shop user (vásárlói) MVP — JWT + bcrypt; az admin login ettől független marad. ---


class UserCreate(BaseModel):
    """Regisztráció MVP: csak e-mail + jelszó (és opcionális megerősítés). Profil a /users/me PATCH-sel."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    password_confirm: str | None = Field(
        None,
        max_length=128,
        description="Ha kitöltöd, meg kell egyeznie a jelszóval.",
    )
    company_website: str | None = Field(None, max_length=256, description="Honeypot — üresen hagyandó.")

    @field_validator("company_website", mode="before")
    @classmethod
    def honeypot_register(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str) and v.strip():
            raise ValueError("Érvénytelen kérés.")
        return None

    @model_validator(mode="after")
    def passwords_match(self):
        pc = self.password_confirm
        if pc is not None and str(pc).strip() and self.password != pc:
            raise ValueError("A jelszó és a megerősítés nem egyezik.")
        return self


class UserLogin(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str | None = None
    email: str
    phone: str | None = None
    shipping_address: str | None = None
    billing_address: str | None = None
    short_bio: str | None
    family_note: str | None
    profile_image_url: str | None
    is_active: bool
    is_banned: bool = False
    last_login_at: datetime | None = None
    email_verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    def is_verified(self) -> bool:
        return self.email_verified_at is not None


class UserRegisterResponse(BaseModel):
    """Regisztráció válasz — a user mellett jelzi, ment-e ki a megerősítő levél."""

    user: UserRead
    verification_email_sent: bool
    message: str | None = Field(
        None,
        description="Ha a levél nem ment ki, magyarázó szöveg a kliensnek.",
    )


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str | None = Field(None, min_length=1, max_length=64)
    nickname: str | None = Field(None, max_length=128)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=64)
    shipping_address: str | None = Field(None, max_length=4000)
    billing_address: str | None = Field(None, max_length=4000)
    short_bio: str | None = Field(None, max_length=4000)
    family_note: str | None = Field(None, max_length=4000)
    profile_image_url: str | None = Field(None, max_length=4000)

    @field_validator("profile_image_url")
    @classmethod
    def profile_image_local_path(cls, v: str | None) -> str | None:
        return validate_profile_image_url(v)

    @model_validator(mode="after")
    def at_least_one_field(self) -> UserUpdate:
        if not self.model_fields_set:
            raise ValueError("Legalább egy mezőt meg kell adni a profil módosításához.")
        return self


class UserAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class UserDeleteResponse(BaseModel):
    message: str
    is_active: bool


class ShopUserAdminRead(BaseModel):
    """Vásárlói fiókok listája az adminnak — ``GET /admin/shop-users``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str | None
    email: str
    is_active: bool
    is_banned: bool = False
    is_deleted: bool = False
    email_verified_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime


ShopUserRole = Literal["shop"]


class AdminShopUserListItem(BaseModel):
    """Vásárlói fiók művelet válasz — ``PATCH /admin/users/{id}/…`` (verify, ban, unban)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str | None = None
    email: str
    role: ShopUserRole = "shop"
    is_active: bool
    is_banned: bool = False
    is_deleted: bool = False
    email_verified_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    deleted_at: datetime | None = None

    @computed_field
    def is_verified(self) -> bool:
        return self.email_verified_at is not None

    @computed_field
    def account_status(self) -> Literal["active", "banned", "inactive", "deleted"]:
        if self.is_deleted:
            return "deleted"
        if self.is_banned:
            return "banned"
        if not self.is_active:
            return "inactive"
        return "active"


class AdminUserVerifyBody(BaseModel):
    email_verified: bool
