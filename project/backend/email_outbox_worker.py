"""Process pending email_outbox rows — atomic claim, backoff, dead-letter."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from db_models import EmailOutbox
from email_outbound import send_order_payment_confirmation

_log = logging.getLogger("mesencsi.email_outbox")

_MAX_ATTEMPTS = 5
_BACKOFF_BASE_SEC = 60
_BACKOFF_MAX_SEC = 3600


@dataclass(frozen=True)
class OutboxBatchResult:
    claimed: int = 0
    sent: int = 0
    failed: int = 0
    dead: int = 0

    @property
    def had_errors(self) -> bool:
        return self.failed > 0 or self.dead > 0


def _backoff_seconds(attempts: int) -> int:
    return min(_BACKOFF_BASE_SEC * (2 ** max(0, attempts - 1)), _BACKOFF_MAX_SEC)


def _next_retry_at(attempts: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=_backoff_seconds(attempts))


def _send_payment_confirmation(payload: dict) -> bool:
    return bool(
        send_order_payment_confirmation(
            to_email=str(payload["to_email"]),
            customer_name=str(payload["customer_name"]),
            order_reference=str(payload["order_reference"]),
            lines=[(str(a), int(b), int(c)) for a, b, c in payload["lines"]],
            products_grand_total_huf=int(
                payload.get("products_grand_total_huf") or payload.get("grand_total_huf", 0)
            ),
            shipping_method_label=payload.get("shipping_method_label"),
            shipping_package_label_hu=payload.get("shipping_package_label_hu"),
            shipping_price_huf=int(payload.get("shipping_price_huf") or 0),
            shipping_address_plain=payload.get("shipping_address_plain"),
            grand_total_huf=int(payload["grand_total_huf"]),
            payment_id=str(payload["payment_id"]),
        )
    )


def _claim_outbox_rows(db: Session, *, limit: int) -> list[EmailOutbox]:
    """Atomically claim rows ready for delivery (PostgreSQL: SKIP LOCKED)."""
    now = datetime.now(UTC)
    lim = max(1, limit)
    dialect = db.get_bind().dialect.name

    candidate = (
        select(EmailOutbox.id)
        .where(
            EmailOutbox.status.in_(("pending", "failed")),
            EmailOutbox.attempts < _MAX_ATTEMPTS,
            or_(EmailOutbox.next_retry_at.is_(None), EmailOutbox.next_retry_at <= now),
        )
        .order_by(EmailOutbox.id.asc())
        .limit(lim)
    )
    if dialect == "postgresql":
        candidate = candidate.with_for_update(skip_locked=True)
    else:
        candidate = candidate.with_for_update()

    ids = list(db.scalars(candidate).all())
    if not ids:
        return []

    stmt = (
        update(EmailOutbox)
        .where(EmailOutbox.id.in_(ids), EmailOutbox.status.in_(("pending", "failed")))
        .values(status="processing", claimed_at=now)
        .returning(EmailOutbox)
    )
    return list(db.scalars(stmt).all())


def _finalize_row_success(row: EmailOutbox) -> None:
    row.status = "sent"
    row.sent_at = datetime.now(UTC)
    row.last_error = None
    row.next_retry_at = None
    row.claimed_at = None


def _finalize_row_failure(row: EmailOutbox, error: str) -> str:
    row.attempts = int(row.attempts or 0) + 1
    row.last_error = error[:2000]
    row.claimed_at = None
    if row.attempts >= _MAX_ATTEMPTS:
        row.status = "dead"
        row.next_retry_at = None
        return "dead"
    row.status = "failed"
    row.next_retry_at = _next_retry_at(row.attempts)
    return "failed"


def process_email_outbox_batch(db: Session, *, limit: int = 20) -> OutboxBatchResult:
    """Claim and process up to ``limit`` outbox rows."""
    rows = _claim_outbox_rows(db, limit=limit)
    result = OutboxBatchResult(claimed=len(rows))
    if not rows:
        return result

    sent = failed = dead = 0
    for row in rows:
        try:
            if row.kind == "payment_confirmation":
                ok = _send_payment_confirmation(dict(row.payload_json))
            else:
                raise RuntimeError(f"Unknown outbox kind: {row.kind}")
            if ok:
                _finalize_row_success(row)
                sent += 1
            else:
                outcome = _finalize_row_failure(row, "SMTP not configured or send skipped")
                if outcome == "dead":
                    dead += 1
                else:
                    failed += 1
        except Exception as exc:
            _log.exception("email_outbox_send_failed id=%s kind=%s", row.id, row.kind)
            outcome = _finalize_row_failure(row, str(exc))
            if outcome == "dead":
                dead += 1
            else:
                failed += 1

    db.commit()
    return OutboxBatchResult(claimed=result.claimed, sent=sent, failed=failed, dead=dead)


def requeue_dead_letters(
    db: Session,
    *,
    dedupe_keys: list[str] | None = None,
    limit: int = 100,
) -> int:
    """Move ``dead`` rows back to ``pending`` for manual replay."""
    now = datetime.now(UTC)
    q = (
        select(EmailOutbox)
        .where(EmailOutbox.status == "dead")
        .order_by(EmailOutbox.id.asc())
        .limit(max(1, limit))
    )
    if dedupe_keys:
        q = q.where(EmailOutbox.dedupe_key.in_(dedupe_keys))
    rows = list(db.scalars(q).all())
    for row in rows:
        row.status = "pending"
        row.attempts = 0
        row.last_error = None
        row.next_retry_at = None
        row.claimed_at = None
        row.sent_at = None
        row.updated_at = now
    if rows:
        db.commit()
    return len(rows)
