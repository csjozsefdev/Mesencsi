"""POST /orders idempotency for guest checkout (keyed by normalized email)."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from db_models import GuestOrderIdempotency, ShopOrder
from idempotency_key import parse_idempotency_key_header
from models import Order
from shop_email import normalize_shop_email


def _payload_hash(order: Order) -> str:
    canonical = order.model_dump(mode="json")
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def lookup_guest_idempotent_orders(
    db: Session, *, guest_email: str, idempotency_key: str, order: Order
) -> tuple[list[ShopOrder] | None, bool]:
    key = parse_idempotency_key_header(idempotency_key)
    if not key:
        return None, False
    email = normalize_shop_email(guest_email)
    row = db.scalar(
        select(GuestOrderIdempotency).where(
            GuestOrderIdempotency.guest_email == email,
            GuestOrderIdempotency.idempotency_key == key,
        )
    )
    if row is None:
        return None, False
    req_hash = _payload_hash(order)
    if row.payload_hash != req_hash:
        return None, True
    ids = [int(x) for x in row.order_ids_json]
    rows = list(db.scalars(select(ShopOrder).where(ShopOrder.id.in_(ids))).all())
    if len(rows) != len(ids):
        return None, False
    return rows, False


def store_guest_idempotent_orders(
    db: Session,
    *,
    guest_email: str,
    idempotency_key: str,
    order: Order,
    order_ids: list[int],
) -> None:
    if not idempotency_key:
        return
    db.add(
        GuestOrderIdempotency(
            guest_email=normalize_shop_email(guest_email),
            idempotency_key=idempotency_key,
            payload_hash=_payload_hash(order),
            order_ids_json=list(order_ids),
        )
    )
