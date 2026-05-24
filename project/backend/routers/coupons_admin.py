"""Admin kupon kezelés — csak owner írhat, listázás maintenance+owner."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from coupon_service import ensure_user_exists, normalize_coupon_code
from database import get_db
from db_models import Coupon as CouponRow
from dependencies import CurrentAdmin, require_role
from models import CouponCreate, CouponRead, CouponUpdate

router = APIRouter(prefix="/coupons", tags=["admin-coupons"])


def _find_coupon(db: Session, coupon_id: int) -> CouponRow:
    row = db.get(CouponRow, coupon_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen kupon.")
    return row


@router.get("", response_model=list[CouponRead])
def admin_list_coupons(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    return list(db.scalars(select(CouponRow).order_by(CouponRow.id.desc())).all())


@router.post("", response_model=CouponRead, status_code=status.HTTP_201_CREATED)
def admin_create_coupon(
    payload: CouponCreate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    code = normalize_coupon_code(payload.code)
    if payload.user_id is not None:
        ensure_user_exists(db, payload.user_id)
    row = CouponRow(
        code=code,
        percent_discount=payload.percent_discount,
        user_id=payload.user_id,
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


@router.patch("/{coupon_id}", response_model=CouponRead)
def admin_update_coupon(
    coupon_id: int,
    payload: CouponUpdate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = _find_coupon(db, coupon_id)
    data = payload.model_dump(exclude_unset=True)
    if "code" in data and data["code"] is not None:
        row.code = normalize_coupon_code(str(data["code"]))
    if "percent_discount" in data:
        row.percent_discount = int(data["percent_discount"])
    if "user_id" in data:
        uid = data["user_id"]
        if uid is not None:
            ensure_user_exists(db, int(uid))
        row.user_id = uid
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = bool(data["is_active"])
    if "expires_at" in data:
        row.expires_at = data["expires_at"]
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


@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = _find_coupon(db, coupon_id)
    db.delete(row)
    db.commit()
    return None
