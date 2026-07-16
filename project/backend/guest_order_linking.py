"""Associate completed guest orders with a verified shop account (same email)."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db_models import AppUser, ShopOrder
from shop_email import normalize_shop_email

_log = logging.getLogger("mesencsi.guest_order_linking")


def link_guest_orders_to_verified_user(db: Session, user: AppUser, *, commit: bool = False) -> int:
    """
    After verified email ownership, attach paid guest orders (user_id IS NULL)
    that match the account email. Never links unpaid or unverified accounts.
    """
    if user.email_verified_at is None:
        return 0
    email = normalize_shop_email(user.email or "")
    if not email:
        return 0
    rows = list(
        db.scalars(
            select(ShopOrder).where(
                ShopOrder.user_id.is_(None),
                func.lower(func.coalesce(ShopOrder.customer_email, "")) == email,
                ShopOrder.payment_status == "paid",
            )
        ).all()
    )
    if not rows:
        return 0
    for row in rows:
        row.user_id = user.id
    if commit:
        db.commit()
    _log.info(
        "guest_orders_linked user_id=%s email=%s count=%s",
        user.id,
        email,
        len(rows),
    )
    return len(rows)
