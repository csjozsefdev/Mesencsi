import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi.responses import FileResponse
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
try:
    from starlette.middleware.proxy_headers import ProxyHeadersMiddleware  # type: ignore
except Exception:  # pragma: no cover
    ProxyHeadersMiddleware = None  # type: ignore[assignment]
from sqlalchemy import select, text
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
from models import (
    Order,
    OrderEstimateLine,
    OrderEstimateRequest,
    OrderEstimateResponse,
    OrderResponse,
    Product,
    StoryRead,
)
from routers.cart import router as cart_router
from routers.gallery import router as gallery_router
from routers.health import router as health_router
from routers.incidents import router as incidents_router
from routers.news_public import router as news_public_router
from routers.storybooks_public import router as storybooks_public_router
from routers.user_auth import router_auth as user_auth_router
from routers.user_mvp import router_users
from routers.payments_barion import router as payments_barion_router
from dependencies import (
    get_current_app_user,
    require_email_verified_shop_user,
    require_email_verified_to_place_order,
)
from services import find_order_owned, find_product
from shipping_address import ShippingAddressValidationError, parse_and_validate_shipping_address_raw
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


def _priced_lines_to_estimate_response(priced) -> OrderEstimateResponse:
    return OrderEstimateResponse(
        discount_percent=priced.discount_percent,
        coupon_code=priced.coupon_code,
        bundle_rule_name=priced.bundle_rule_name,
        bundle_discount_total=priced.bundle_discount_total,
        bundle_percent=priced.bundle_percent,
        lines=[_priced_line_to_estimate_line(pl) for pl in priced.lines],
        grand_original=priced.grand_original,
        grand_discount=priced.grand_discount,
        grand_final=priced.grand_final,
    )


def _persist_discount_amount(pl) -> int | None:
    """Return discount_amount for DB, or None when no discount applies to the line."""
    disc_amt = pl.discount_amount
    disc_pct = pl.discount_percent
    return disc_amt if (disc_amt or disc_pct is not None or pl.coupon_code) else None


def _priced_line_to_shop_order(
    pl,
    *,
    user_id: int,
    customer_name: str,
    buyer_email: str,
    shipping_normalized: str,
    notes: str | None,
    checkout_group_id: str,
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
        notes=notes,
        status="new",
        payment_status="pending",
        checkout_group_id=checkout_group_id,
        bundle_rule_id=pl.bundle_rule_id,
        bundle_rule_name=pl.bundle_rule_name,
        bundle_discount_amount=pl.bundle_discount_amount,
    )


def _compute_order_estimate(db: Session, user_id: int, payload: OrderEstimateRequest) -> OrderEstimateResponse:
    """Kosár + kombó kedvezmény és/vagy kupon — csak számolás, nincs DB írás (kombó elsőbbsége a kuponnal szemben)."""
    priced = compute_checkout_pricing(db, user_id=user_id, items=payload.items, coupon_code=payload.coupon_code)
    return _priced_lines_to_estimate_response(priced)


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
    user: AppUser = Depends(get_current_app_user),
):
    """Kosár összesítő kuponnal — a szerver számolja az árakat (a kliens árát nem fogadjuk el)."""
    return _compute_order_estimate(db, user.id, payload)


@app.post("/orders", response_model=list[OrderResponse], status_code=201)
@limiter.limit("25/minute")
def create_order(
    request: Request,
    order: Order,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_email_verified_to_place_order),
):
    """Kosár checkout: JWT + megerősített e-mail; a user a tokenből jön. Inaktív fiók: 401."""
    buyer_email = (user.email or "").strip()
    if not buyer_email:
        raise HTTPException(
            status_code=422,
            detail="Hiányzó e-mail a fiókodból — frissítsd a profilodat.",
        )
    try:
        shipping_normalized = parse_and_validate_shipping_address_raw(
            order.shipping_address,
            required=True,
        )
    except ShippingAddressValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not shipping_normalized:
        raise HTTPException(status_code=422, detail="A szállítási cím megadása kötelező.")

    priced = compute_checkout_pricing(db, user_id=user.id, items=order.items, coupon_code=order.coupon_code)

    checkout_group_id = str(uuid.uuid4())
    customer_name = order.customer_name.strip()
    order_notes = order.notes.strip() if order.notes else None
    rows: list[ShopOrder] = []
    for pl in priced.lines:
        row = _priced_line_to_shop_order(
            pl,
            user_id=user.id,
            customer_name=customer_name,
            buyer_email=buyer_email,
            shipping_normalized=shipping_normalized,
            notes=order_notes,
            checkout_group_id=checkout_group_id,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for r in rows:
        db.refresh(r)
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
