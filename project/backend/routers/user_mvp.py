"""Vásárlói profil MVP: kuponok, avatar, profil szerkesztés, soft delete."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth_limits import limiter
from database import get_db
from db_models import AppUser, Coupon
from dependencies import get_current_app_user, require_email_verified_shop_user
from email_outbound import send_email_verification
from image_upload import delete_uploaded_file_by_url, save_uploaded_image
from models import CouponPublicRead, UserDeleteResponse, UserRead, UserUpdate
from routers.user_auth import (
    FORGOT_PASSWORD_GENERIC_MSG,
    RESET_PASSWORD_INVALID_MSG,
    _duplicate_message,
    router_auth,
)
from shipping_address import (
    ShippingAddressValidationError,
    validate_hu_phone,
    validate_optional_profile_address_raw,
)
from user_email_verify import assign_verification_to_user, issue_verification_token

router_users = APIRouter(prefix="/users", tags=["users"])
_log = logging.getLogger("mesencsi.user_profile")

__all__ = [
    "router_users",
]


@router_users.get("/me/coupons", response_model=list[CouponPublicRead])
@limiter.limit("60/minute")
def list_my_active_coupons(
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_email_verified_shop_user),
):
    """Saját, aktív és nem lejárt, userhez rendelt kuponok (globális kódok nincsenek itt felsorolva)."""
    now = datetime.now(UTC)
    stmt = (
        select(Coupon)
        .where(
            Coupon.user_id == user.id,
            Coupon.is_active.is_(True),
            (Coupon.expires_at.is_(None)) | (Coupon.expires_at > now),
        )
        .order_by(Coupon.id.desc())
    )
    return list(db.scalars(stmt).all())


@router_users.get("/me", response_model=UserRead)
def users_me_alias(user: AppUser = Depends(get_current_app_user)):
    """Ugyanaz, mint ``GET /auth/me`` — alternatív útvonal a kliensek számára."""
    return user


@router_users.post("/me/avatar", response_model=UserRead)
@limiter.limit("20/minute")
async def upload_my_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_app_user),
):
    """Profilkép feltöltése — ``media/uploads/avatars`` (közös MIME + méret validáció)."""
    prev = user.profile_image_url
    try:
        url, _filename = await save_uploaded_image(file, subdir="avatars", filename_prefix=f"user-{int(user.id)}")
    except HTTPException:
        raise
    user.profile_image_url = url
    try:
        db.commit()
    except Exception:
        db.rollback()
        delete_uploaded_file_by_url(url)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nem sikerült elmenteni a profilképet. Próbáld újra.",
        ) from None
    db.refresh(user)
    if prev and str(prev).strip() and str(prev).strip() != url.strip():
        delete_uploaded_file_by_url(prev)
    return user


@router_users.patch("/me", response_model=UserRead)
def patch_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_app_user),
):
    data = payload.model_dump(exclude_unset=True)
    prev_email = user.email
    reverify_token: str | None = None
    if "username" in data and data["username"] is not None:
        user.username = str(data["username"]).strip()
    if "nickname" in data:
        raw = data.get("nickname")
        user.nickname = (str(raw).strip() if raw is not None else "") or None
    if "email" in data and data["email"] is not None:
        em = str(data["email"]).strip()
        if not em:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Az e-mail cím nem lehet üres.",
            )
        if em != prev_email:
            user.email = em
            reverify_token = issue_verification_token()
            assign_verification_to_user(db, user, reverify_token)
    if "short_bio" in data:
        sb = data.get("short_bio")
        user.short_bio = None if sb is None else (str(sb).strip() or None)
    if "family_note" in data:
        fn = data.get("family_note")
        user.family_note = None if fn is None else (str(fn).strip() or None)
    if "profile_image_url" in data:
        pu = data.get("profile_image_url")
        user.profile_image_url = None if pu is None else (str(pu).strip() or None)
    if "phone" in data:
        ph = data.get("phone")
        if ph is None:
            user.phone = None
        else:
            raw_ph = str(ph).strip()
            if not raw_ph:
                user.phone = None
            else:
                try:
                    user.phone = validate_hu_phone(raw_ph)
                except ShippingAddressValidationError as e:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=str(e),
                    ) from e
    if "shipping_address" in data:
        sa = data.get("shipping_address")
        try:
            user.shipping_address = validate_optional_profile_address_raw(
                None if sa is None else (str(sa).strip() or None)
            )
        except ShippingAddressValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e
    if "billing_address" in data:
        ba = data.get("billing_address")
        try:
            user.billing_address = validate_optional_profile_address_raw(
                None if ba is None else (str(ba).strip() or None)
            )
        except ShippingAddressValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_duplicate_message(e)) from e
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adatbázis hiba — próbáld újra egy kicsit később.",
        ) from None
    db.refresh(user)
    if reverify_token:
        try:
            send_email_verification(user.email, reverify_token)
        except Exception as e:
            _log.exception("Verification email failed after email change: %s", e)
    return user


@router_users.delete("/me", response_model=UserDeleteResponse)
def soft_delete_me(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_app_user),
):
    user.is_active = False
    user.is_deleted = True
    user.deleted_at = datetime.now(UTC)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nem sikerült a fiók deaktiválása. Próbáld újra.",
        ) from None
    db.refresh(user)
    return UserDeleteResponse(message="A fiók inaktiválva lett.", is_active=user.is_active)
