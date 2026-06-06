"""Authenticated user shopping cart (server-side persistence)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database import get_db
from db_models import AppUser, Product as ProductRow, UserCartItem
from dependencies import get_current_app_user
from models import CartLineRead, CartPutRequest

router = APIRouter(prefix="/cart", tags=["cart"])


def _read_lines(db: Session, user_id: int) -> list[CartLineRead]:
    rows = db.execute(
        select(UserCartItem, ProductRow)
        .join(ProductRow, ProductRow.id == UserCartItem.product_id)
        .where(UserCartItem.user_id == user_id)
        .order_by(UserCartItem.product_id.asc())
    ).all()
    out: list[CartLineRead] = []
    for cart_row, product in rows:
        q = int(cart_row.quantity)
        if q < 1:
            continue
        out.append(
            CartLineRead(
                product_id=int(product.id),
                quantity=q,
                name=str(product.name),
                price=int(product.price),
                description=str(product.description or ""),
            )
        )
    return out


@router.get("", response_model=list[CartLineRead])
def get_user_cart(
    user: AppUser = Depends(get_current_app_user),
    db: Session = Depends(get_db),
) -> list[CartLineRead]:
    return _read_lines(db, user.id)


@router.put("", response_model=list[CartLineRead])
def replace_user_cart(
    payload: CartPutRequest,
    user: AppUser = Depends(get_current_app_user),
    db: Session = Depends(get_db),
) -> list[CartLineRead]:
    # Merge duplicate product_ids in payload (last wins).
    merged: dict[int, int] = {}
    for line in payload.items:
        pid = int(line.product_id)
        qty = int(line.quantity)
        if qty < 1:
            continue
        merged[pid] = min(qty, 999)

    if merged:
        existing = list(
            db.scalars(select(ProductRow.id).where(ProductRow.id.in_(list(merged.keys())))).all()
        )
        missing = set(merged.keys()) - set(existing)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Egy vagy több termék nem létezik.",
            )

    db.execute(delete(UserCartItem).where(UserCartItem.user_id == user.id))
    for pid, qty in sorted(merged.items()):
        db.add(UserCartItem(user_id=user.id, product_id=pid, quantity=qty))
    db.commit()
    return _read_lines(db, user.id)


def clear_user_cart(db: Session, user_id: int) -> None:
    """Remove all server-side cart lines for a user (e.g. after checkout order created)."""
    db.execute(delete(UserCartItem).where(UserCartItem.user_id == user_id))
