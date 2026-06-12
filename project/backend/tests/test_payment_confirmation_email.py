"""Fizetés-visszaigazoló e-mail: csak verify után, duplikátum nélkül, hiba nem állítja meg a sync-et."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from db_models import ShopOrder
from mesencsi import app
from payment_confirmation_email import PaymentConfirmationSnapshot, _format_order_reference
from tests.test_checkout_bundle_integration import (
    _auth_headers,
    _checkout_order_body,
    _seed_verified_user_and_products,
)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_format_order_reference_checkout_group() -> None:
    class _Row:
        id = 1
        checkout_group_id = "cg-abc-123"

    assert _format_order_reference([_Row()]) == "cg-abc-123"


def test_payment_confirmation_sent_once_on_duplicate_ipn(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BARION_POS_KEY", "test-pos-key-16chars")
    monkeypatch.setenv("BARION_PAYEE_EMAIL", "payee@example.com")
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Email Teszt", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    oid = int(r.json()[0]["id"])
    with patch("routers.payments_barion.start_payment_request", return_value={"PaymentId": "pay-email-001"}):
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    pid = br.json()["payment_id"]

    fake_state = {"Status": "Succeeded"}
    with patch("routers.payments_barion.get_payment_state", return_value=fake_state):
        with patch(
            "routers.payments_barion.schedule_payment_confirmation_after_paid_sync"
        ) as mock_schedule:
            monkeypatch.setenv("BARION_IPN_SECRET", "ipn-secret-test-16b")
            assert (
                client.post(
                    "/payments/barion/ipn?barion_ipn=ipn-secret-test-16b",
                    json={"PaymentId": pid},
                ).status_code
                == 200
            )
            assert (
                client.post(
                    "/payments/barion/ipn?barion_ipn=ipn-secret-test-16b",
                    json={"PaymentId": pid},
                ).status_code
                == 200
            )
            assert mock_schedule.call_count == 1

    db = SessionLocal()
    try:
        assert db.get(ShopOrder, oid).payment_status == "paid"
    finally:
        db.close()


def test_payment_confirmation_email_failure_does_not_break_ipn(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BARION_POS_KEY", "test-pos-key-16chars")
    monkeypatch.setenv("BARION_PAYEE_EMAIL", "payee@example.com")
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Email Fail", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    oid = int(r.json()[0]["id"])
    with patch("routers.payments_barion.start_payment_request", return_value={"PaymentId": "pay-email-002"}):
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Succeeded"}):
        with patch(
            "routers.payments_barion.schedule_payment_confirmation_after_paid_sync",
            side_effect=RuntimeError("email scheduler broke"),
        ):
            monkeypatch.setenv("BARION_IPN_SECRET", "ipn-secret-test-16b")
            resp = client.post(
                "/payments/barion/ipn?barion_ipn=ipn-secret-test-16b",
                json={"PaymentId": "pay-email-002"},
            )
    assert resp.status_code == 200
    db = SessionLocal()
    try:
        assert db.get(ShopOrder, oid).payment_status == "paid"
    finally:
        db.close()


def test_send_order_payment_confirmation_builds_body() -> None:
    with patch("email_outbound.send_plain_email", return_value=True) as mock_send:
        from email_outbound import send_order_payment_confirmation

        ok = send_order_payment_confirmation(
            to_email="buyer@example.com",
            customer_name="Teszt Elek",
            order_reference="cg-xyz",
            lines=[("Könyv A", 2, 3000)],
            grand_total_huf=3000,
            payment_id="barion-pay-99",
        )
        assert ok is True
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs["to_email"] == "buyer@example.com"
        assert "Teszt Elek" in kwargs["body"]
        assert "cg-xyz" in kwargs["body"]
        assert "3 000" in kwargs["body"]
        assert "Könyv A" in kwargs["body"]


def test_outbox_worker_failure_does_not_raise() -> None:
    from db_models import EmailOutbox
    from email_outbox_worker import process_email_outbox_batch

    db = SessionLocal()
    try:
        db.add(
            EmailOutbox(
                dedupe_key="payment_confirmation:pay-fail-01",
                kind="payment_confirmation",
                payload_json={
                    "to_email": "a@b.c",
                    "customer_name": "Név",
                    "order_reference": "#1",
                    "lines": [["Termék", 1, 100]],
                    "grand_total_huf": 100,
                    "payment_id": "pay-fail-01",
                },
                status="pending",
            )
        )
        db.commit()
        with patch("email_outbox_worker.send_order_payment_confirmation", side_effect=OSError("smtp down")):
            result = process_email_outbox_batch(db, limit=1)
        assert result.failed == 1
        row = db.scalar(
            __import__("sqlalchemy").select(EmailOutbox).where(
                EmailOutbox.dedupe_key == "payment_confirmation:pay-fail-01"
            )
        )
        assert row is not None
        assert row.status == "failed"
    finally:
        db.close()
