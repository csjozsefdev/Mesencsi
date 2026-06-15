"""Payment confirmation email outbox dedupe, claim, backoff, dead-letter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from database import SessionLocal
from db_models import EmailOutbox, ShopOrder
from email_outbox_worker import (
    _MAX_ATTEMPTS,
    OutboxBatchResult,
    process_email_outbox_batch,
    requeue_dead_letters,
)
from payment_confirmation_email import enqueue_payment_confirmation_outbox


def test_outbox_dedupe_key_prevents_duplicate() -> None:
    db = SessionLocal()
    try:
        rows = [
            ShopOrder(
                id=1,
                user_id=1,
                product_id=1,
                product_name="Book",
                quantity=1,
                total_price=1000,
                customer_name="Teszt",
                customer_email="buyer@example.com",
                checkout_group_id="cg-1",
                status="new",
                payment_status="paid",
            )
        ]
        assert enqueue_payment_confirmation_outbox(db, "pay-dedupe-01", rows) is True
        db.commit()
        assert enqueue_payment_confirmation_outbox(db, "pay-dedupe-01", rows) is False
        count = db.scalar(select(EmailOutbox).where(EmailOutbox.dedupe_key == "payment_confirmation:pay-dedupe-01"))
        assert count is not None
    finally:
        db.close()


def test_outbox_processor_marks_sent() -> None:
    db = SessionLocal()
    try:
        db.add(
            EmailOutbox(
                dedupe_key="payment_confirmation:pay-proc-01",
                kind="payment_confirmation",
                payload_json={
                    "to_email": "buyer@example.com",
                    "customer_name": "Teszt",
                    "order_reference": "cg-1",
                    "lines": [["Book", 1, 1000]],
                    "grand_total_huf": 1000,
                    "payment_id": "pay-proc-01",
                },
                status="pending",
            )
        )
        db.commit()
        with patch("email_outbox_worker.send_order_payment_confirmation", return_value=True):
            result = process_email_outbox_batch(db, limit=5)
        assert result == OutboxBatchResult(claimed=1, sent=1, failed=0, dead=0)
        row = db.scalar(select(EmailOutbox).where(EmailOutbox.dedupe_key == "payment_confirmation:pay-proc-01"))
        assert row is not None
        assert row.status == "sent"
        assert row.sent_at is not None
    finally:
        db.close()


def test_outbox_backoff_on_failure() -> None:
    db = SessionLocal()
    try:
        db.add(
            EmailOutbox(
                dedupe_key="payment_confirmation:pay-backoff-01",
                kind="payment_confirmation",
                payload_json={
                    "to_email": "buyer@example.com",
                    "customer_name": "Teszt",
                    "order_reference": "cg-1",
                    "lines": [["Book", 1, 1000]],
                    "grand_total_huf": 1000,
                    "payment_id": "pay-backoff-01",
                },
                status="pending",
            )
        )
        db.commit()
        with patch("email_outbox_worker.send_order_payment_confirmation", return_value=False):
            result = process_email_outbox_batch(db, limit=1)
        assert result.failed == 1
        row = db.scalar(select(EmailOutbox).where(EmailOutbox.dedupe_key == "payment_confirmation:pay-backoff-01"))
        assert row is not None
        assert row.status == "failed"
        assert row.attempts == 1
        assert row.next_retry_at is not None
    finally:
        db.close()


def test_outbox_dead_letter_after_max_attempts() -> None:
    db = SessionLocal()
    try:
        row = EmailOutbox(
            dedupe_key="payment_confirmation:pay-dead-01",
            kind="payment_confirmation",
            payload_json={
                "to_email": "buyer@example.com",
                "customer_name": "Teszt",
                "order_reference": "cg-1",
                "lines": [["Book", 1, 1000]],
                "grand_total_huf": 1000,
                "payment_id": "pay-dead-01",
            },
            status="pending",
            attempts=_MAX_ATTEMPTS - 1,
        )
        db.add(row)
        db.commit()
        with patch("email_outbox_worker.send_order_payment_confirmation", side_effect=RuntimeError("smtp")):
            result = process_email_outbox_batch(db, limit=1)
        assert result.dead == 1
        db.refresh(row)
        assert row.status == "dead"
        assert row.attempts == _MAX_ATTEMPTS
    finally:
        db.close()


def test_outbox_skips_until_next_retry_at() -> None:
    db = SessionLocal()
    try:
        db.add(
            EmailOutbox(
                dedupe_key="payment_confirmation:pay-wait-01",
                kind="payment_confirmation",
                payload_json={
                    "to_email": "buyer@example.com",
                    "customer_name": "Teszt",
                    "order_reference": "cg-1",
                    "lines": [["Book", 1, 1000]],
                    "grand_total_huf": 1000,
                    "payment_id": "pay-wait-01",
                },
                status="failed",
                attempts=1,
                next_retry_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        db.commit()
        result = process_email_outbox_batch(db, limit=5)
        assert result.claimed == 0
    finally:
        db.close()


def test_requeue_dead_letters() -> None:
    db = SessionLocal()
    try:
        db.add(
            EmailOutbox(
                dedupe_key="payment_confirmation:pay-req-01",
                kind="payment_confirmation",
                payload_json={"to_email": "a@b.c"},
                status="dead",
                attempts=_MAX_ATTEMPTS,
                last_error="gave up",
            )
        )
        db.commit()
        n = requeue_dead_letters(db, dedupe_keys=["payment_confirmation:pay-req-01"])
        assert n == 1
        row = db.scalar(select(EmailOutbox).where(EmailOutbox.dedupe_key == "payment_confirmation:pay-req-01"))
        assert row is not None
        assert row.status == "pending"
        assert row.attempts == 0
        assert row.last_error is None
    finally:
        db.close()
