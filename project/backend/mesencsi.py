import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi.responses import FileResponse
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
try:
    from starlette.middleware.proxy_headers import ProxyHeadersMiddleware  # type: ignore
except Exception:  # pragma: no cover
    ProxyHeadersMiddleware = None  # type: ignore[assignment]
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from auth_limits import limiter
from csrf import CsrfMiddleware
from database import engine, get_db
from db_models import AppUser, PaymentAttempt, Product as ProductRow, ShopOrder, Story as StoryRow
from incident_support import register_incident_support
from metrics_support import MetricsMiddleware, metrics_endpoint
from security_headers import register_security_headers
from admin_routes import router as admin_router
from bundle_discount_service import compute_checkout_pricing
from policy_versions import PRIVACY_POLICY_VERSION, TERMS_VERSION
from models import (
    Order,
    OrderEstimateLine,
    OrderEstimateRequest,
    OrderEstimateResponse,
    OrderResponse,
    Product,
    StoryRead,
)
from idempotency_key import IdempotencyKeyError, parse_idempotency_key_header
from order_idempotency import lookup_idempotent_orders, store_idempotent_orders
from routers.cart import router as cart_router
from routers.gallery import router as gallery_router
from routers.health import router as health_router
from routers.incidents import router as incidents_router
from routers.news_public import router as news_public_router
from routers.storybooks_public import router as storybooks_public_router
from routers.user_auth import router_auth as user_auth_router
from routers.user_mvp import router_users
from routers.payments_barion import router as payments_barion_router
from routers.shop_public import router as shop_public_router
from dependencies import (
    get_current_app_user,
    get_optional_app_user,
    require_email_verified_shop_user,
)
from guest_checkout_tokens import guest_checkout_token_header_name, issue_guest_checkout_token
from guest_order_idempotency import lookup_guest_idempotent_orders, store_guest_idempotent_orders
from shop_email import normalize_shop_email
from services import find_order_owned, find_product
from shipping_methods import (
    GLS_HOME,
    count_shippable_item_quantity,
    normalize_shipping_method,
    parse_shipping_metadata_field,
    recommend_gls_shipping,
    resolve_order_shipping,
    resolve_shipping_price_huf,
)
from auth import log_admin_auth_startup
from cors_config import resolve_cors_allow_origins
from frontend_assets import ensure_page_background_at_startup
from openapi_docs import fastapi_openapi_kwargs
from order_guards import assert_order_line_deletable
from email_config import log_smtp_config_at_startup
from routers.dev_diagnostics import router as dev_diagnostics_router
from startup_config import run_startup_config_validation
from user_tokens import log_user_jwt_startup


def _priced_line_to_estimate_line(pl) -> OrderEstimateLine:
    return OrderEstimateLine(
        product_id=pl.product_id,
        product_name=pl.product_name,
        quantity=pl.quantity,
        original_total=pl.original_total,
        discount_amount=pl.discount_amount,
        final_total=pl.final_total,
        bundle_discount_amount=pl.bundle_discount_amount,
    )


def _priced_lines_to_estimate_response(
    priced,
    *,
    shipping_method: str,
    shipping_price: int,
    shippable_item_count: int = 0,
    shipping_package_label_hu: str | None = None,
    shipping_recommended_package_label_hu: str | None = None,
) -> OrderEstimateResponse:
    products_final = priced.grand_final
    return OrderEstimateResponse(
        discount_percent=priced.discount_percent,
        coupon_code=priced.coupon_code,
        bundle_rule_name=priced.bundle_rule_name,
        bundle_discount_total=priced.bundle_discount_total,
        bundle_percent=priced.bundle_percent,
        lines=[_priced_line_to_estimate_line(pl) for pl in priced.lines],
        grand_original=priced.grand_original,
        grand_discount=priced.grand_discount,
        products_grand_final=products_final,
        shipping_method=shipping_method,
        shipping_price=shipping_price,
        shipping_package_label_hu=shipping_package_label_hu,
        shipping_recommended_package_label_hu=shipping_recommended_package_label_hu,
        shippable_item_count=shippable_item_count,
        grand_final=products_final + shipping_price,
    )


def _persist_discount_amount(pl) -> int | None:
    """Return discount_amount for DB, or None when no discount applies to the line."""
    disc_amt = pl.discount_amount
    disc_pct = pl.discount_percent
    return disc_amt if (disc_amt or disc_pct is not None or pl.coupon_code) else None


def _priced_line_to_shop_order(
    pl,
    *,
    user_id: int | None,
    customer_name: str,
    buyer_email: str,
    shipping_normalized: str | None,
    shipping_method: str,
    shipping_price: int,
    shipping_metadata: dict | None,
    notes: str | None,
    checkout_group_id: str,
    accepted_at: datetime,
) -> ShopOrder:
    return ShopOrder(
        user_id=user_id,
        product_id=pl.product_id,
        product_name=pl.product_name,
        quantity=pl.quantity,
        total_price=pl.final_total,
        original_total=pl.original_total,
        discount_percent=pl.discount_percent,
        discount_amount=_persist_discount_amount(pl),
        coupon_code=pl.coupon_code,
        customer_name=customer_name,
        customer_email=buyer_email,
        shipping_address=shipping_normalized,
        shipping_method=shipping_method,
        shipping_price=shipping_price,
        shipping_metadata_json=shipping_metadata,
        notes=notes,
        status="new",
        payment_status="pending",
        checkout_group_id=checkout_group_id,
        bundle_rule_id=pl.bundle_rule_id,
        bundle_rule_name=pl.bundle_rule_name,
        bundle_discount_amount=pl.bundle_discount_amount,
        terms_accepted_at=accepted_at,
        terms_version=TERMS_VERSION,
        privacy_acknowledged_at=accepted_at,
        privacy_version=PRIVACY_POLICY_VERSION,
    )


def _compute_order_estimate(db: Session, user_id: int | None, payload: OrderEstimateRequest) -> OrderEstimateResponse:
    """Kosár + kombó kedvezmény és/vagy kupon — csak számolás, nincs DB írás (kombó elsőbbsége a kuponnal szemben)."""
    shipping_method = normalize_shipping_method(payload.shipping_method)
    shippable_count = count_shippable_item_quantity(payload.items)
    shipping_price = resolve_shipping_price_huf(
        shipping_method,
        shippable_item_count=shippable_count,
    )
    package_label: str | None = None
    if shipping_method == GLS_HOME:
        _tier, _price, package_label = recommend_gls_shipping(shippable_count)
    priced = compute_checkout_pricing(db, user_id=user_id, items=payload.items, coupon_code=payload.coupon_code)
    return _priced_lines_to_estimate_response(
        priced,
        shipping_method=shipping_method,
        shipping_price=shipping_price,
        shippable_item_count=shippable_count,
        shipping_package_label_hu=package_label,
    )


def _resolve_checkout_user(
    user: AppUser | None,
) -> tuple[int | None, str, bool]:
    """Returns (user_id, buyer_email, is_guest). Raises HTTPException on invalid guest/auth state."""
    if user is not None:
        if user.email_verified_at is None:
            raise HTTPException(
                status_code=403,
                detail="A rendelés leadásához erősítsd meg az e-mail címed.",
            )
        buyer_email = (user.email or "").strip()
        if not buyer_email:
            raise HTTPException(
                status_code=422,
                detail="Hiányzó e-mail a fiókodból — frissítsd a profilodat.",
            )
        return user.id, buyer_email, False
    return None, "", True


def _configure_logging() -> None:
    if logging.root.handlers:
        return
    level_name = (os.environ.get("LOG_LEVEL") or os.environ.get("MESENCSI_LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    run_startup_config_validation()
    log_smtp_config_at_startup()
    ensure_page_background_at_startup()
    log_user_jwt_startup()
    log_admin_auth_startup()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    from shop_qa_bootstrap import ensure_qa_shop_user

    ensure_qa_shop_user()
    yield


# Production (MESENCSI_PRODUCTION): no public /docs, /redoc, or /openapi.json.
app = FastAPI(lifespan=lifespan, **fastapi_openapi_kwargs())
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
register_incident_support(app)
app.include_router(health_router)
app.include_router(dev_diagnostics_router)
app.include_router(incidents_router)
app.include_router(gallery_router)
app.include_router(user_auth_router)
app.include_router(router_users)
app.include_router(cart_router)
app.include_router(payments_barion_router)
app.include_router(news_public_router)
app.include_router(storybooks_public_router)
app.include_router(shop_public_router)

app.add_middleware(MetricsMiddleware)

def _proxy_trusted_hosts() -> str | list[str]:
    """Comma-separated hosts for X-Forwarded-* trust (default: loopback only)."""
    raw = (os.environ.get("TRUSTED_PROXY_HOSTS") or "").strip()
    if not raw:
        return "127.0.0.1"
    if raw == "*":
        return "*"
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts if len(parts) > 1 else (parts[0] if parts else "127.0.0.1")


if ProxyHeadersMiddleware is not None:
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=_proxy_trusted_hosts())
app.add_middleware(CsrfMiddleware)


# Production: ``CORS_ALLOWED_ORIGINS`` (vagy ``ALLOWED_ORIGINS``) — vesszővel elválasztott lista, nincs wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=resolve_cors_allow_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
# Outermost on the response path so headers apply after CORS and request-id middleware.
register_security_headers(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "frontend"))


@app.get("/")
def read_index():
    path = os.path.join(FRONTEND_DIR, "mesencsi.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="A kezdőlap fájlja nem található a szerveren.")
    return FileResponse(path)


@app.get("/mesencsi.html")
def read_mesencsi_alias():
    """Alias for static-server habits; same storefront as ``/``."""
    return read_index()


def _serve_storefront_shell():
    """Shared handler for legal/hash SPA routes — frontend renders the view."""
    return read_index()


@app.get("/aszf")
def read_aszf_page():
    """SPA route: serve storefront shell and let the frontend render."""
    return _serve_storefront_shell()


@app.get("/adatkezeles")
def read_adatkezeles_page():
    """SPA route: serve storefront shell and let the frontend render."""
    return _serve_storefront_shell()


@app.get("/internal/metrics")
def internal_metrics(request: Request):
    return metrics_endpoint(request)


@app.get("/impresszum")
def read_impresszum_page():
    """SPA route: serve storefront shell and let the frontend render."""
    return _serve_storefront_shell()


@app.get("/elallas")
def read_elallas_page():
    return _serve_storefront_shell()


@app.get("/szallitas")
def read_szallitas_page():
    return _serve_storefront_shell()


@app.get("/fizetes")
def read_fizetes_page():
    return _serve_storefront_shell()


@app.get("/panaszkezeles")
def read_panaszkezeles_page():
    return _serve_storefront_shell()


@app.get("/sutik")
def read_sutik_page():
    return _serve_storefront_shell()


@app.get("/site.webmanifest", include_in_schema=False)
def site_web_manifest():
    """PWA manifest; explicit route so MIME is ``application/manifest+json`` on all hosts."""
    path = os.path.join(FRONTEND_DIR, "site.webmanifest")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Manifest not found.")
    return FileResponse(path, media_type="application/manifest+json")


def _admin_html_no_cache_headers() -> dict[str, str]:
    """Admin HTML gyakran változik fejlesztés közben — ne ragadjon be a böngésző cache."""
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }


@app.get("/admin/login")
def admin_login_page():
    path = os.path.join(FRONTEND_DIR, "admin-login.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Az admin belépő oldal nem található.")
    return FileResponse(path, headers=_admin_html_no_cache_headers())


@app.get("/admin")
def admin_dashboard_page():
    path = os.path.join(FRONTEND_DIR, "admin.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Az admin kezelőfelület nem található.")
    return FileResponse(path, headers=_admin_html_no_cache_headers())


@app.get("/admin/dashboard")
def admin_dashboard_alias():
    """Optional URL; same dashboard as ``GET /admin``."""
    return admin_dashboard_page()


app.include_router(admin_router)


@app.get("/products", response_model=list[Product])
def get_products(db: Session = Depends(get_db)):
    return db.scalars(select(ProductRow).order_by(ProductRow.id)).all()


@app.get("/stories", response_model=list[StoryRead])
def get_stories_public(db: Session = Depends(get_db)):
    """Mesék szövegei a látogatói oldalhoz (sorrend: sort_order, majd id)."""
    return db.scalars(select(StoryRow).order_by(StoryRow.sort_order.asc(), StoryRow.id.asc())).all()


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return find_product(db, product_id)


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_email_verified_shop_user),
):
    return find_order_owned(db, order_id, user.id)


@app.post("/orders/estimate", response_model=OrderEstimateResponse)
@limiter.limit("45/minute")
def estimate_order_checkout(
    request: Request,
    payload: OrderEstimateRequest,
    db: Session = Depends(get_db),
    user: AppUser | None = Depends(get_optional_app_user),
):
    """Cart pricing with bundle/coupon — server-side only. Auth optional (coupons require login)."""
    user_id = user.id if user is not None else None
    if payload.coupon_code and user_id is None:
        raise HTTPException(
            status_code=403,
            detail="A kuponok csak bejelentkezett, e-mailben megerősített fiókkal használhatók.",
        )
    if payload.coupon_code and user is not None and user.email_verified_at is None:
        raise HTTPException(
            status_code=403,
            detail="A kuponok csak megerősített e-mail című fiókkal használhatók. Ellenőrizd a postafiókodat.",
        )
    return _compute_order_estimate(db, user_id, payload)


@app.post("/orders", response_model=list[OrderResponse], status_code=201)
@limiter.limit("25/minute")
def create_order(
    request: Request,
    response: Response,
    order: Order,
    db: Session = Depends(get_db),
    user: AppUser | None = Depends(get_optional_app_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Checkout: authenticated (verified email) or guest (customer_email in body)."""
    try:
        normalized_idem_key = parse_idempotency_key_header(idempotency_key)
    except IdempotencyKeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    is_guest = user is None
    buyer_email = ""
    user_id: int | None = None

    if is_guest:
        guest_email_raw = (order.customer_email or "").strip()
        if not guest_email_raw:
            raise HTTPException(
                status_code=422,
                detail="Vendég vásárláshoz az e-mail cím megadása kötelező.",
            )
        buyer_email = normalize_shop_email(guest_email_raw)
        if order.coupon_code:
            raise HTTPException(
                status_code=403,
                detail="A kuponok csak bejelentkezett, e-mailben megerősített fiókkal használhatók.",
            )
        if normalized_idem_key:
            existing, conflict = lookup_guest_idempotent_orders(
                db,
                guest_email=buyer_email,
                idempotency_key=normalized_idem_key,
                order=order,
            )
            if conflict:
                raise HTTPException(
                    status_code=409,
                    detail="Az idempotency kulcs már más checkout tartalommal lett használva.",
                )
            if existing is not None:
                return existing
    else:
        assert user is not None
        user_id, buyer_email, _ = _resolve_checkout_user(user)
        if normalized_idem_key:
            existing, conflict = lookup_idempotent_orders(
                db,
                user_id=int(user_id),
                idempotency_key=normalized_idem_key,
                order=order,
            )
            if conflict:
                raise HTTPException(
                    status_code=409,
                    detail="Az idempotency kulcs már más checkout tartalommal lett használva.",
                )
            if existing is not None:
                return existing

    shipping_metadata = parse_shipping_metadata_field(order.shipping_metadata)
    shippable_count = count_shippable_item_quantity(order.items)
    customer_name = order.customer_name.strip()
    shipping_method, shipping_price, shipping_normalized, shipping_metadata = resolve_order_shipping(
        method_raw=order.shipping_method,
        shipping_address_raw=order.shipping_address,
        shipping_metadata=shipping_metadata,
        shippable_item_count=shippable_count,
        customer_name=customer_name,
    )

    priced = compute_checkout_pricing(db, user_id=user_id, items=order.items, coupon_code=order.coupon_code)

    checkout_group_id = str(uuid.uuid4())
    accepted_at = datetime.now(UTC)
    origin/main
    order_notes = order.notes.strip() if order.notes else None
    rows: list[ShopOrder] = []
    for pl in priced.lines:
        row = _priced_line_to_shop_order(
            pl,
            user_id=user_id,
            customer_name=customer_name,
            buyer_email=buyer_email,
            shipping_normalized=shipping_normalized,
            shipping_method=shipping_method,
            shipping_price=shipping_price,
            shipping_metadata=shipping_metadata,
            notes=order_notes,
            checkout_group_id=checkout_group_id,
            accepted_at=accepted_at,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    if normalized_idem_key:
        if is_guest:
            store_guest_idempotent_orders(
                db,
                guest_email=buyer_email,
                idempotency_key=normalized_idem_key,
                order=order,
                order_ids=[int(r.id) for r in rows],
            )
        else:
            store_idempotent_orders(
                db,
                user_id=int(user_id),
                idempotency_key=normalized_idem_key,
                order=order,
                order_ids=[int(r.id) for r in rows],
            )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if normalized_idem_key:
            if is_guest:
                raced, conflict = lookup_guest_idempotent_orders(
                    db,
                    guest_email=buyer_email,
                    idempotency_key=normalized_idem_key,
                    order=order,
                )
            else:
                raced, conflict = lookup_idempotent_orders(
                    db,
                    user_id=int(user_id),
                    idempotency_key=normalized_idem_key,
                    order=order,
                )
            if conflict:
                raise HTTPException(
                    status_code=409,
                    detail="Az idempotency kulcs már más checkout tartalommal lett használva.",
                ) from exc
            if raced is not None:
                return raced
        raise
    for r in rows:
        db.refresh(r)
    if is_guest:
        response.headers[guest_checkout_token_header_name()] = issue_guest_checkout_token(checkout_group_id)
    return rows


@app.get("/orders", response_model=list[OrderResponse])
def get_orders(
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_email_verified_shop_user),
):
    return db.scalars(
        select(ShopOrder).where(ShopOrder.user_id == user.id).order_by(ShopOrder.id)
    ).all()


@app.delete("/orders/{order_id}", status_code=204)
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_email_verified_shop_user),
):
    order_row = find_order_owned(db, order_id, user.id)
    assert_order_line_deletable(db, order_row)
    db.delete(order_row)
    db.commit()
    return None


# Route registration order (do not reorder without updating tests/test_route_registration.py):
# 1) include_router(*) and @app routes above — API, admin HTML, storefront shell paths
# 2) /media StaticFiles — uploaded assets
# 3) / frontend StaticFiles — catch-all for css/js/images (html=False; no SPA fallback for unknown paths)
_MEDIA_DIR = os.path.join(BASE_DIR, "media")
os.makedirs(os.path.join(_MEDIA_DIR, "uploads"), exist_ok=True)
app.mount("/media", StaticFiles(directory=_MEDIA_DIR, html=False), name="media")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=False), name="frontend")
