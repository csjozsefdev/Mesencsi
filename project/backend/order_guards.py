"""Shared order-line delete guards (shop user + admin)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db_models import PaymentAttempt, ShopOrder


def assert_order_line_deletable(db: Session, row: ShopOrder) -> None:
    """Raise HTTP 409 when the order line must not be deleted."""
    ps = (row.payment_status or "pending").strip().lower()
    if ps == "paid":
        raise HTTPException(status_code=409, detail="Fizetett rendelés nem törölhető.")
    if (row.barion_payment_id or "").strip() and ps == "pending":
        raise HTTPException(
            status_code=409,
            detail="Függő Barion fizetésű rendelés nem törölhető.",
        )
    cg = (row.checkout_group_id or "").strip()
    if cg:
        active = db.scalar(
            select(PaymentAttempt.id).where(
                PaymentAttempt.checkout_group_id == cg,
                PaymentAttempt.is_active.is_(True),
                PaymentAttempt.status == "pending",
            )
        )
        if active is not None:
            raise HTTPException(
                status_code=409,
                detail="Aktív fizetési kísérlet tartozik ehhez a checkout csoporthoz — törlés nem engedélyezett.",
            )
