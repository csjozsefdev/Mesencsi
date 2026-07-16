"""Fizetés-visszaigazoló e-mail — DB outbox; csak pending→paid átmenet után."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app_logging import get_request_id, log_event
from db_models import EmailOutbox, ShopOrder
from email_outbox_worker import process_email_outbox_batch
from shipping_methods import (
    checkout_group_grand_total_huf,
    checkout_group_products_total_huf,
    gls_package_label_from_metadata,
    parse_shipping_metadata_field,
    shipping_method_label_hu,
)
from shipping_address import format_shipping_address_plain

_log = logging.getLogger("mesencsi.payment_email")


@dataclass(frozen=True)
class PaymentConfirmationSnapshot:
    payment_id: str
    to_email: str
    customer_name: str
    order_reference: str
    lines: tuple[tuple[str, int, int], ...]
    products_grand_total_huf: int
    shipping_method: str | None
    shipping_method_label: str | None
    shipping_package_label_hu: str | None
    shipping_price_huf: int
    shipping_address_plain: str | None
    grand_total_huf: int


def _format_order_reference(rows: list[ShopOrder]) -> str:
    gid = (rows[0].checkout_group_id or "").strip() if rows else ""
    if gid:
        return gid
    ids = sorted({int(r.id) for r in rows})
    if len(ids) == 1:
        return f"#{ids[0]}"
    return "#" + ", #".join(str(i) for i in ids)


def _snapshot_from_orders(payment_id: str, rows: list[ShopOrder]) -> PaymentConfirmationSnapshot | None:
    if not rows:
        return None
    to_email = (rows[0].customer_email or "").strip()
    if not to_email:
        return None
    customer_name = (rows[0].customer_name or "Vásárló").strip() or "Vásárló"
    lines = tuple((r.product_name, int(r.quantity), int(r.total_price)) for r in rows)
    products_grand = checkout_group_products_total_huf(rows)
    shipping_price = max(int(getattr(r, "shipping_price", 0) or 0) for r in rows)
    method = (rows[0].shipping_method or "").strip() or None
    method_label = shipping_method_label_hu(method) if method else None
    metadata = parse_shipping_metadata_field(getattr(rows[0], "shipping_metadata_json", None))
    package_label = gls_package_label_from_metadata(metadata)
    address_plain = format_shipping_address_plain(getattr(rows[0], "shipping_address", None))
    if not address_plain.strip():
        address_plain = None
    grand = checkout_group_grand_total_huf(rows)
    return PaymentConfirmationSnapshot(
        payment_id=payment_id,
        to_email=to_email,
        customer_name=customer_name,
        order_reference=_format_order_reference(rows),
        lines=lines,
        products_grand_total_huf=products_grand,
        shipping_method=method,
        shipping_method_label=method_label,
        shipping_package_label_hu=package_label,
        shipping_price_huf=shipping_price,
        shipping_address_plain=address_plain,
        grand_total_huf=grand,
    )


def enqueue_payment_confirmation_outbox(db: Session, payment_id: str, rows: list[ShopOrder]) -> bool:
    """Insert outbox row in the current transaction. Returns True if a new row was queued."""
    snapshot = _snapshot_from_orders(payment_id, rows)
    if snapshot is None:
        log_event(
            _log,
            logging.WARNING,
            "payment_confirmation_email_skipped_no_recipient",
            request_id=get_request_id(),
            payment_id=payment_id[:16],
        )
        return False
    dedupe_key = f"payment_confirmation:{payment_id}"
    payload = {
        "to_email": snapshot.to_email,
        "customer_name": snapshot.customer_name,
        "order_reference": snapshot.order_reference,
        "lines": [list(line) for line in snapshot.lines],
        "products_grand_total_huf": snapshot.products_grand_total_huf,
        "shipping_method": snapshot.shipping_method,
        "shipping_method_label": snapshot.shipping_method_label,
        "shipping_package_label_hu": snapshot.shipping_package_label_hu,
        "shipping_price_huf": snapshot.shipping_price_huf,
        "shipping_address_plain": snapshot.shipping_address_plain,
        "grand_total_huf": snapshot.grand_total_huf,
        "payment_id": snapshot.payment_id,
    }
    db.add(
        EmailOutbox(
            dedupe_key=dedupe_key,
            kind="payment_confirmation",
            payload_json=payload,
            status="pending",
        )
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        log_event(
            _log,
            logging.INFO,
            "payment_confirmation_email_duplicate_skipped",
            request_id=get_request_id(),
            payment_id=payment_id[:16],
        )
        return False
    return True


def schedule_payment_confirmation_after_paid_sync(payment_id: str, rows: list[ShopOrder]) -> None:
    """
    Csak akkor hívandó, ha a sync **most** állította paid-re a sorokat.
    Outbox rekordot ír, majd megpróbálja azonnal feldolgozni (SMTP hiba nem állítja vissza a paid státuszt).
    """
    from database import SessionLocal

    db = SessionLocal()
    try:
        if not enqueue_payment_confirmation_outbox(db, payment_id, rows):
            return
        db.commit()
        result = process_email_outbox_batch(db, limit=1)
        if result.had_errors:
            _log.warning(
                "payment_confirmation_outbox_batch_errors sent=%s failed=%s dead=%s",
                result.sent,
                result.failed,
                result.dead,
            )
    except Exception:
        db.rollback()
        _log.exception("payment_confirmation_outbox_enqueue_failed payment_id=%s", payment_id[:16])
    finally:
        db.close()
