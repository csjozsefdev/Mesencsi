"""Kupon feloldás és soronkénti kedvezmény számítás (szerveroldali, Ft egész)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from db_models import AppUser, Coupon


def normalize_coupon_code(raw: str) -> str:
    return raw.strip().upper()


def resolve_usable_coupon(db: Session, *, code: str, user_id: int) -> Coupon:
    """Aktív, nem lejárt kupon; userhez kötött esetén csak a megadott user használhatja."""
    u = ensure_user_exists(db, user_id)
    if u.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A kuponok csak megerősített e-mail című fiókkal használhatók. Ellenőrizd a postafiókodat vagy kérj új megerősítő levelet.",
        )
    norm = normalize_coupon_code(code)
    if not norm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Adj meg egy kuponkódot.",
        )
    row = db.scalar(select(Coupon).where(Coupon.code == norm))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nincs ilyen kuponkód.",
        )
    if not row.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ez a kupon inaktív.",
        )
    if row.expires_at is not None:
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if exp < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ez a kupon lejárt.",
            )
    if row.user_id is not None and row.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ez a kupon nem a te fiókodhoz tartozik.",
        )
    _require_percent_discount_in_range(int(row.percent_discount))
    return row


def _require_percent_discount_in_range(percent: object) -> int:
    """Egész százalék 1–100; minden API és kuponfeloldás ezt követeli (0, negatív és 100 felett elutasítva)."""
    try:
        p = int(percent)
    except (TypeError, ValueError):
        p = -1
    if p < 1 or p > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A kupon kedvezménye csak 1 és 100 közötti egész százalék lehet (0, negatív és 100 feletti érték nem engedélyezett).",
        )
    return p


def line_amounts_with_discount(original_subtotal: int, percent: int) -> tuple[int, int, int]:
    """Vissza: (discount_amount, final_subtotal, percent). A százalékot nem „javítjuk” csendben."""
    if original_subtotal < 0:
        raise ValueError("original_subtotal")
    p = _require_percent_discount_in_range(percent)
    discount = (original_subtotal * p) // 100
    final = original_subtotal - discount
    return discount, final, p


def ensure_user_exists(db: Session, user_id: int) -> AppUser:
    row = db.get(AppUser, user_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen felhasználó.")
    return row
