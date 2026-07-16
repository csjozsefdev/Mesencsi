from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app_logging import get_request_id, log_event
from auth import admin_shell_usernames
from database import get_db, storybook_tables_exist
from coupon_service import ensure_user_exists, normalize_coupon_code
from auth_limits import limiter
from image_upload import delete_uploaded_file_by_url, save_uploaded_image
from order_guards import assert_order_line_deletable
from db_models import (
    AppUser,
    Coupon,
    DigitalStorybook,
    GalleryItem,
    Incident,
    NewsComment,
    NewsPost,
    PaymentAttempt,
    Product as ProductRow,
    ShopOrder,
    Story,
)
from dependencies import CurrentAdmin, require_role
from email_outbound import send_email_verification
from models import (
    AdminImageUploadResponse,
    AdminOrderStatusPatch,
    AdminShopUserListItem,
    AdminUserVerifyBody,
    ShopUserAdminRead,
    CouponRead,
    GalleryItemCreate,
    GalleryItemRead,
    GalleryItemUpdate,
    IncidentRead,
    OrderResponse,
    Product,
    ProductCreate,
    ProductUpdate,
    StoryCreate,
    StoryRead,
    StoryUpdate,
    UserDiscountAssignCreate,
)
from services import find_gallery_row, find_order, find_product, find_story
from user_email_verify import assign_verification_to_user, issue_verification_token
from routers.admin_auth import router as admin_auth_router
from routers.bundle_discounts_admin import router as bundle_discounts_admin_router
from routers.news_admin import router as news_admin_router
from routers.storybooks_admin import router as storybooks_admin_router


router = APIRouter(prefix="/admin", tags=["admin"])
_admin_log = logging.getLogger("mesencsi.admin")
router.include_router(admin_auth_router)
router.include_router(news_admin_router)
router.include_router(storybooks_admin_router)
router.include_router(bundle_discounts_admin_router)


def _protected_shop_emails_for_admin_actions() -> set[str]:
    """Törölés/tiltás tiltása — ``MESENCSI_PROTECTED_SHOP_EMAILS=viz@viz.hu,masik@x.hu`` + auth userek e-mail formátumú neve."""
    out: set[str] = set()
    raw = os.environ.get("MESENCSI_PROTECTED_SHOP_EMAILS", "").strip()
    for part in raw.split(","):
        p = part.strip().lower()
        if p:
            out.add(p)
    for un_raw in admin_shell_usernames():
        un = str(un_raw).strip().lower()
        if "@" in un:
            out.add(un)
    return out


def _get_shop_user_for_admin(db: Session, user_id: int) -> AppUser:
    row = db.get(AppUser, user_id)
    if row is None or row.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen felhasználó.")
    return row


def _assert_shop_user_destructive_allowed(user: AppUser, admin: CurrentAdmin) -> None:
    prot = _protected_shop_emails_for_admin_actions()
    em = user.email.strip().lower()
    if em in prot:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ez a vásárlói fiók védett — nem törölhető és nem tiltható az admin felületről.",
        )
    if em == admin.username.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nem végezhetsz törlést vagy tiltást ezen a fiókon (admin azonosító egyezik az e-maillel).",
        )


@router.get("/orders", response_model=list[OrderResponse])
def admin_orders(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    return db.scalars(select(ShopOrder).order_by(ShopOrder.id.desc())).all()


@router.patch("/orders/{order_id}", response_model=OrderResponse)
def admin_patch_order_status(
    order_id: int,
    payload: AdminOrderStatusPatch,
    db: Session = Depends(get_db),
    admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    row = find_order(db, order_id)
    if payload.payment_status is not None and admin.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A fizetési állapot kézi módosítása csak tulajdonosi jogosultsággal engedélyezett.",
        )
    if payload.status is not None:
        if payload.status == "completed":
            payment_ps = (row.payment_status or "pending").strip().lower()
            if payment_ps != "paid":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Csak fizetett rendelés teljesíthető.",
                )
        row.status = payload.status
    if payload.payment_status is not None:
        new_ps = payload.payment_status
        if new_ps == "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A „Fizetve” állapot adminból nem állítható — csak Barion szerveres ellenőrzés után.",
            )
        bp = (row.barion_payment_id or "").strip()
        if bp and new_ps in ("paid", "failed", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Barion fizetésnél a fizetési állapot csak return/IPN/GetPaymentState szinkron után frissül.",
            )
        row.payment_status = new_ps
    db.commit()
    db.refresh(row)
    return row


@router.delete("/orders/{order_id}", status_code=204)
def admin_delete_order_line(
    order_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    """Egy rendelési sor törlése (egy checkout több sorból állhat — mindegyik külön törölhető)."""
    row = find_order(db, order_id)
    assert_order_line_deletable(db, row)
    db.delete(row)
    db.commit()
    return None


@router.get("/shop-users", response_model=list[ShopUserAdminRead])
def admin_list_shop_users(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
    limit: int = 200,
):
    """Vásárlói fiókok listája — canonical endpoint (az admin UI is ezt hívja)."""
    limit = max(1, min(limit, 500))
    stmt = (
        select(AppUser)
        .where(AppUser.is_deleted.is_(False))
        .order_by(AppUser.id.desc())
        .limit(limit)
    )
    return db.scalars(stmt).all()


@router.patch("/users/{user_id}/verify", response_model=AdminShopUserListItem)
def admin_patch_user_verify(
    user_id: int,
    payload: AdminUserVerifyBody,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    user = _get_shop_user_for_admin(db, user_id)
    if payload.email_verified:
        user.email_verified_at = datetime.now(UTC)
        user.email_verification_token = None
        user.email_verification_sent_at = None
    else:
        user.email_verified_at = None
        user.email_verification_token = None
        user.email_verification_sent_at = None
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/ban", response_model=AdminShopUserListItem)
def admin_ban_shop_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    user = _get_shop_user_for_admin(db, user_id)
    _assert_shop_user_destructive_allowed(user, admin)
    user.is_banned = True
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/unban", response_model=AdminShopUserListItem)
def admin_unban_shop_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    user = _get_shop_user_for_admin(db, user_id)
    user.is_banned = False
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def admin_soft_delete_shop_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen felhasználó.")
    if user.is_deleted:
        return None
    _assert_shop_user_destructive_allowed(user, admin)
    user.is_deleted = True
    user.deleted_at = datetime.now(UTC)
    user.is_active = False
    db.commit()
    return None


@router.post("/users/{user_id}/resend-verification")
def admin_resend_user_verification_email(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    user = _get_shop_user_for_admin(db, user_id)
    if user.email_verified_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Az e-mail cím már megerősítve van.",
        )
    token = issue_verification_token()
    assign_verification_to_user(db, user, token)
    db.commit()
    db.refresh(user)
    try:
        ok = send_email_verification(user.email, token)
    except Exception as e:
        _admin_log.exception("Admin resend verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nem sikerült elküldeni az e-mailt.",
        ) from e
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Az e-mail küldés nincs konfigurálva (SMTP).",
        )
    return {"ok": True}


@router.get("/products", response_model=list[Product])
def admin_products(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    return db.scalars(select(ProductRow).order_by(ProductRow.id)).all()


@router.post("/products", response_model=Product, status_code=201)
def admin_create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = ProductRow(
        name=payload.name.strip(),
        price=payload.price,
        description=(payload.description or "").strip() or "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/products/{product_id}", response_model=Product)
def admin_update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_product(db, product_id)
    if payload.name is not None:
        row.name = payload.name.strip()
    if payload.price is not None:
        row.price = payload.price
    if payload.description is not None:
        row.description = payload.description.strip()
    db.commit()
    db.refresh(row)
    return row


@router.delete("/products/{product_id}", status_code=204)
def admin_delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_product(db, product_id)
    img = row.image_url
    cnt = db.scalar(select(func.count()).select_from(ShopOrder).where(ShopOrder.product_id == product_id))
    if cnt and int(cnt) > 0:
        raise HTTPException(
            status_code=409,
            detail="Ehhez a termékhez tartoznak rendelések — nem törölhető.",
        )
    db.delete(row)
    db.commit()
    delete_uploaded_file_by_url(img)
    return None


@router.post("/products/{product_id}/image", response_model=AdminImageUploadResponse)
async def admin_upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_product(db, product_id)
    prev = row.image_url
    url, filename = await save_uploaded_image(file, subdir="products", filename_prefix=f"product-{product_id}")
    row.image_url = url
    db.commit()
    if prev and str(prev).strip() and str(prev).strip() != url.strip():
        delete_uploaded_file_by_url(prev)
    return AdminImageUploadResponse(url=url, filename=filename)


@router.post("/gallery/upload", response_model=AdminImageUploadResponse)
async def admin_upload_gallery_image(
    file: UploadFile = File(...),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    """Kép mentése ``media/uploads/gallery`` alá; a válasz ``url`` mezője a galéria rekordhoz."""
    try:
        url, filename = await save_uploaded_image(file, subdir="gallery", filename_prefix="gallery")
    except HTTPException as e:
        if e.status_code == 415:
            log_event(
                _admin_log,
                logging.INFO,
                "admin_upload_rejected",
                request_id=get_request_id(),
                reason="unsupported_or_invalid_image",
            )
        raise
    return AdminImageUploadResponse(url=url, filename=filename)


@router.get("/gallery", response_model=list[GalleryItemRead])
def admin_gallery(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    return db.scalars(select(GalleryItem).order_by(GalleryItem.sort_order.asc(), GalleryItem.id.asc())).all()


@router.post("/gallery", response_model=GalleryItemRead, status_code=201)
def admin_create_gallery_item(
    payload: GalleryItemCreate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = GalleryItem(
        title=payload.title.strip(),
        image_url=payload.image_url.strip(),
        description=payload.description.strip() if payload.description else None,
        sort_order=payload.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/gallery/{item_id}", response_model=GalleryItemRead)
def admin_update_gallery_item(
    item_id: int,
    payload: GalleryItemUpdate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_gallery_row(db, item_id)
    if payload.title is not None:
        row.title = payload.title.strip()
    if payload.image_url is not None:
        new_u = payload.image_url.strip()
        old_u = (row.image_url or "").strip()
        if new_u != old_u:
            delete_uploaded_file_by_url(row.image_url)
        row.image_url = new_u
    if payload.description is not None:
        row.description = payload.description.strip() if payload.description else None
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    db.commit()
    db.refresh(row)
    return row


@router.delete("/gallery/{item_id}", status_code=204)
def admin_delete_gallery_item(
    item_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_gallery_row(db, item_id)
    img = row.image_url
    db.delete(row)
    db.commit()
    delete_uploaded_file_by_url(img)
    return None


@router.post("/gallery/{item_id}/image", response_model=AdminImageUploadResponse)
async def admin_replace_gallery_item_image(
    item_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_gallery_row(db, item_id)
    prev = row.image_url
    url, filename = await save_uploaded_image(file, subdir="gallery", filename_prefix=f"gallery-{item_id}")
    row.image_url = url
    db.commit()
    if prev and str(prev).strip() and str(prev).strip() != url.strip():
        delete_uploaded_file_by_url(prev)
    return AdminImageUploadResponse(url=url, filename=filename)


@router.get("/stories", response_model=list[StoryRead])
def admin_stories(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    return db.scalars(select(Story).order_by(Story.sort_order.asc(), Story.id.asc())).all()


@router.post("/stories", response_model=StoryRead, status_code=201)
def admin_create_story(
    payload: StoryCreate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = Story(
        title=payload.title.strip(),
        body=payload.body.strip(),
        sort_order=payload.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/stories/{story_id}", response_model=StoryRead)
def admin_update_story(
    story_id: int,
    payload: StoryUpdate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_story(db, story_id)
    if payload.title is not None:
        row.title = payload.title.strip()
    if payload.body is not None:
        row.body = payload.body.strip()
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    db.commit()
    db.refresh(row)
    return row


@router.delete("/stories/{story_id}", status_code=204)
def admin_delete_story(
    story_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = find_story(db, story_id)
    db.delete(row)
    db.commit()
    return None


@router.get("/logs", response_model=list[IncidentRead])
def admin_logs(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance"])),
    limit: int = 50,
):
    limit = max(1, min(limit, 200))
    return db.scalars(select(Incident).order_by(Incident.created_at.desc()).limit(limit)).all()


@router.post("/users/{user_id}/discounts", response_model=CouponRead, status_code=status.HTTP_201_CREATED)
def admin_assign_user_discount(
    user_id: int,
    payload: UserDiscountAssignCreate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    """Személyre szabott kupon létrehozása a megadott vásárlóhoz."""
    ensure_user_exists(db, user_id)
    code = normalize_coupon_code(payload.code)
    row = Coupon(
        code=code,
        percent_discount=payload.percent_discount,
        user_id=user_id,
        is_active=payload.is_active,
        expires_at=payload.expires_at,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ez a kuponkód már foglalt.",
        ) from None
    db.refresh(row)
    return row


@router.get("/system")
def admin_system(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance"])),
):
    products = db.scalar(select(func.count()).select_from(ProductRow))
    orders = db.scalar(select(func.count()).select_from(ShopOrder))
    stories = db.scalar(select(func.count()).select_from(Story))
    news_posts = db.scalar(select(func.count()).select_from(NewsPost))
    news_comments = db.scalar(select(func.count()).select_from(NewsComment))
    if storybook_tables_exist(db):
        storybooks = db.scalar(select(func.count()).select_from(DigitalStorybook))
    else:
        logging.getLogger(__name__).warning(
            "admin /system: digital_storybooks missing — storybooks count set to 0 (run: alembic upgrade head)"
        )
        storybooks = 0
    return {
        "status": "ok",
        "counts": {
            "products": products,
            "orders": orders,
            "stories": stories,
            "news_posts": news_posts,
            "news_comments": news_comments,
            "storybooks": storybooks,
        },
    }
