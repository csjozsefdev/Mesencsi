"""Fizetés-visszaigazoló e-mail — csak Barion GetPaymentState verify + pending→paid átmenet után."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from app_logging import get_request_id, log_event
from db_models import ShopOrder
from email_outbound import send_order_payment_confirmation

_log = logging.getLogger("mesencsi.payment_email")


@dataclass(frozen=True)
class PaymentConfirmationSnapshot:
    payment_id: str
    to_email: str
    customer_name: str
    order_reference: str
    lines: tuple[tuple[str, int, int], ...]
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
    grand = sum(int(r.total_price) for r in rows)
    return PaymentConfirmationSnapshot(
        payment_id=payment_id,
        to_email=to_email,
        customer_name=customer_name,
        order_reference=_format_order_reference(rows),
        lines=lines,
        grand_total_huf=grand,
    )


def _send_from_snapshot(snapshot: PaymentConfirmationSnapshot) -> None:
    """Háttérszálon vagy szinkronban — nem dob kivételt a hívó felé."""
    rid = get_request_id()
    try:
        sent = send_order_payment_confirmation(
            to_email=snapshot.to_email,
            customer_name=snapshot.customer_name,
            order_reference=snapshot.order_reference,
            lines=list(snapshot.lines),
            grand_total_huf=snapshot.grand_total_huf,
            payment_id=snapshot.payment_id,
        )
        if sent:
            log_event(
                _log,
                logging.INFO,
                "payment_confirmation_email_sent",
                request_id=rid,
                payment_id=snapshot.payment_id[:16],
                order_reference=snapshot.order_reference,
                to_domain=snapshot.to_email.split("@")[-1] if "@" in snapshot.to_email else "?",
            )
        else:
            log_event(
                _log,
                logging.INFO,
                "payment_confirmation_email_skipped_no_smtp",
                request_id=rid,
                payment_id=snapshot.payment_id[:16],
                order_reference=snapshot.order_reference,
            )
    except Exception:
        _log.exception(
            "payment_confirmation_email_failed payment_id=%s order_ref=%s",
            snapshot.payment_id[:16],
            snapshot.order_reference,
        )
        log_event(
            _log,
            logging.ERROR,
            "payment_confirmation_email_failed",
            request_id=rid,
            payment_id=snapshot.payment_id[:16],
            order_reference=snapshot.order_reference,
        )


def schedule_payment_confirmation_after_paid_sync(payment_id: str, rows: list[ShopOrder]) -> None:
    """
    Csak akkor hívandó, ha a sync **most** állította paid-re a sorokat (rows_updated > 0).
    Duplikált IPN/return nem küld újra levelet. A küldés daemon szálon fut — nem blokkolja az IPN választ.
    """
    snapshot = _snapshot_from_orders(payment_id, rows)
    if snapshot is None:
        log_event(
            _log,
            logging.WARNING,
            "payment_confirmation_email_skipped_no_recipient",
            request_id=get_request_id(),
            payment_id=payment_id[:16],
        )
        return
    threading.Thread(
        target=_send_from_snapshot,
        args=(snapshot,),
        name=f"payment-confirm-email-{payment_id[:12]}",
        daemon=True,
    ).start()
