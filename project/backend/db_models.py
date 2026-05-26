from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base


class AppUser(Base):
    """Vásárlói / regisztrált felhasználó (MVP). Az admin login külön táblázat nélkül marad."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(Text(), nullable=True)
    billing_address: Mapped[str | None] = mapped_column(Text(), nullable=True)
    short_bio: Mapped[str | None] = mapped_column(Text(), nullable=True)
    family_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), server_default="true", nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean(), server_default="false", nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean(), server_default="false", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verification_token: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    email_verification_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    password_reset_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_reset_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class LoginThrottle(Base):
    """Sikertelen belépések számolása e-mail szerint (bruteforce védelem)."""

    __tablename__ = "login_throttle"

    email_normalized: Mapped[str] = mapped_column(String(320), primary_key=True)
    failed_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(2000))
    image_url: Mapped[str | None] = mapped_column(Text(), nullable=True)


class UserCartItem(Base):
    """Per-user shopping cart persisted server-side (survives logout/login)."""

    __tablename__ = "user_cart_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_user_cart_user_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ShopOrder(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer)
    total_price: Mapped[int] = mapped_column(Integer)
    original_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coupon_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(Text(), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), server_default="new", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(32), server_default="pending", nullable=False)
    barion_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    checkout_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    bundle_rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_bundle_discounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    bundle_rule_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bundle_discount_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class PaymentAttempt(Base):
    """Barion payment session history per checkout group (supports retry and orphan PaymentId sync)."""

    __tablename__ = "payment_attempts"
    __table_args__ = (
        UniqueConstraint("barion_payment_id", name="uq_payment_attempts_barion_payment_id"),
        UniqueConstraint("payment_request_id", name="uq_payment_attempts_payment_request_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    checkout_group_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    barion_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payment_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), server_default="pending", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean(), server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Coupon(Base):
    """Kedvezménykupon: opcionálisan egy adott vásárlóhoz kötve (user_id)."""

    __tablename__ = "coupons"
    __table_args__ = (
        CheckConstraint(
            "percent_discount >= 1 AND percent_discount <= 100",
            name="coupons_percent_discount_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    percent_discount: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), server_default="true", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


bundle_discount_product_association = Table(
    "bundle_discount_products",
    Base.metadata,
    Column("bundle_discount_id", Integer, ForeignKey("product_bundle_discounts.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
)


class ProductBundleDiscount(Base):
    """Admin által definiált termék-kombó: minden felsorolt termékből legalább 1 db a kosárban → százalékos kedvezmény."""

    __tablename__ = "product_bundle_discounts"
    __table_args__ = (
        CheckConstraint(
            "percent_discount >= 0 AND percent_discount <= 100",
            name="bundle_discount_percent_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    percent_discount: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean(), server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    products: Mapped[list[Product]] = relationship(secondary=bundle_discount_product_association)


class GalleryItem(Base):
    """Illustration / hero image row for the public gallery (paginated API)."""

    __tablename__ = "gallery_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    image_url: Mapped[str] = mapped_column(Text())
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Story(Base):
    """Short story / tale text for the Mesék section (owner-managed)."""

    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text())
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class NewsPost(Base):
    """Hírek / újdonságok — admin által kezelt; a főoldalon hero helyett megjelenhet."""

    __tablename__ = "news_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text())
    body: Mapped[str] = mapped_column(Text())
    image_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false", nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false", nullable=False)
    release_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    author_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class NewsComment(Base):
    """Hírhez tartozó közösségi komment — moderálható; user törlésekor user_id NULL."""

    __tablename__ = "news_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(
        ForeignKey("news_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean(), server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DigitalStorybook(Base):
    """Digitális lapozható mesekönyv — admin kezeli; publikus csak közzétett."""

    __tablename__ = "digital_storybooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean(), server_default="false", nullable=False)
    animation_settings: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DigitalStorybookPage(Base):
    """Egy oldal: szöveg, opcionális kép és narráció URL."""

    __tablename__ = "digital_storybook_pages"
    __table_args__ = (UniqueConstraint("book_id", "page_index", name="uq_storybook_page_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("digital_storybooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_text: Mapped[str] = mapped_column(Text(), nullable=False, server_default="")
    image_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    audio_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    text_position_vertical: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="center"
    )
    text_position_horizontal: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="center"
    )
    text_box_style: Mapped[str] = mapped_column(String(32), nullable=False, server_default="card")
    text_x_percent: Mapped[float | None] = mapped_column(Float(), nullable=True)
    text_y_percent: Mapped[float | None] = mapped_column(Float(), nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Incident(Base):
    """Server-side audit of failures (not exposed to clients as API errors)."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    method: Mapped[str] = mapped_column(String(16))
    path: Mapped[str] = mapped_column(String(2048))
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text())
    traceback: Mapped[str | None] = mapped_column(Text(), nullable=True)
