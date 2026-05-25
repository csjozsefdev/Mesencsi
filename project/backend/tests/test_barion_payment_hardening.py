"""Production hardening: IPN non-2xx on sync failure, PaymentAttempt orphan/retry, idempotent /start, commit recovery."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal
from db_models import PaymentAttempt, ShopOrder
from mesencsi import app
from tests.test_checkout_bundle_integration import (
    _auth_headers,
    _checkout_order_body,
    _seed_verified_user_and_products,
)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _barion_rest_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_POS_KEY", "test-pos-key-16chars")
    monkeypatch.setenv("BARION_PAYEE_EMAIL", "payee@example.com")


def _start_barion_payment(client: TestClient, uid: int, oid: int, *, payment_id: str = "pay-hard-001") -> str:
    with patch("routers.payments_barion.start_payment_request", return_value={"PaymentId": payment_id}):
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br.status_code == 200, br.text
    return br.json()["payment_id"]


def test_ipn_sync_failure_returns_non_2xx(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_IPN_SECRET", "ipn-shared-secret-20")
    monkeypatch.setenv("BARION_POS_KEY", "test-pos-key-16chars-xx")
    monkeypatch.setenv("BARION_PAYEE_EMAIL", "payee@example.com")

    def _sync_boom(db, pid: str) -> None:
        raise RuntimeError("sync boom")

    monkeypatch.setattr(
        "routers.payments_barion.sync_orders_payment_status_from_barion",
        _sync_boom,
    )
    r = client.post(
        "/payments/barion/ipn?barion_ipn=ipn-shared-secret-20",
        json={"PaymentId": "pay-sync-fail-01"},
    )
    assert r.status_code == 503
    assert "sync" not in (r.json() or {})


def test_orphan_old_payment_id_still_marks_orders_paid(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _barion_rest_env(monkeypatch)
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Orphan Pay", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    assert r.status_code == 201, r.text
    oid = int(r.json()[0]["id"])
    pid_a = _start_barion_payment(client, uid, oid, payment_id="orphan-pay-a")

    db = SessionLocal()
    try:
        row = db.get(ShopOrder, oid)
        assert row is not None
        row.payment_status = "failed"
        db.commit()
    finally:
        db.close()

    with patch("routers.payments_barion.start_payment_request", return_value={"PaymentId": "orphan-pay-b"}):
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br.status_code == 200, br.text
    assert br.json()["payment_id"] == "orphan-pay-b"

    db = SessionLocal()
    try:
        row = db.get(ShopOrder, oid)
        assert row is not None
        assert row.barion_payment_id == "orphan-pay-b"
        assert row.payment_status == "pending"
    finally:
        db.close()

    from sqlalchemy import select

    from routers.payments_barion import sync_orders_payment_status_from_barion

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Succeeded"}):
        db = SessionLocal()
        try:
            shop, _ = sync_orders_payment_status_from_barion(db, pid_a)
            assert shop == "paid"
            row = db.get(ShopOrder, oid)
            assert row is not None
            assert row.payment_status == "paid"
            attempt_a = db.scalar(select(PaymentAttempt).where(PaymentAttempt.barion_payment_id == pid_a))
            assert attempt_a is not None
            assert attempt_a.status == "paid"
            assert attempt_a.is_active is False
        finally:
            db.close()


def test_concurrent_start_second_call_resumes_without_second_barion_api(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _barion_rest_env(monkeypatch)
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Race Start", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    oid = int(r.json()[0]["id"])

    with patch("routers.payments_barion.start_payment_request", return_value={"PaymentId": "race-pay-001"}) as mock_start:
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            r1 = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
            assert r1.status_code == 200
            pid = r1.json()["payment_id"]

            r2 = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
            assert r2.status_code == 200
            assert r2.json()["payment_id"] == pid
            assert r2.json().get("resumed_existing") is True
            assert mock_start.call_count == 1


def test_start_commit_failure_recovery_then_resume(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _barion_rest_env(monkeypatch)
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Commit Fail", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    oid = int(r.json()[0]["id"])

    real_commit = Session.commit
    commit_calls: list[str] = []

    def flaky_commit(self: Session) -> None:
        commit_calls.append("c")
        # Fail the orders+attempt final commit (after attempt row already exists from first commit).
        if len(commit_calls) == 2:
            raise SQLAlchemyError("simulated orders commit failure")
        return real_commit(self)

    monkeypatch.setattr(Session, "commit", flaky_commit)

    with patch("routers.payments_barion.start_payment_request", return_value={"PaymentId": "recover-pay-01"}):
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            br = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br.status_code == 503

    monkeypatch.setattr(Session, "commit", real_commit)

    with patch("routers.payments_barion.start_payment_request", return_value={"PaymentId": "recover-pay-02"}) as mock_start:
        with patch("routers.payments_barion.gateway_redirect_url", return_value="https://barion.test/pay"):
            br2 = client.post("/payments/barion/start", json={"order_ids": [oid]}, headers=_auth_headers(uid))
    assert br2.status_code == 200, br2.text
    assert br2.json()["payment_id"] == "recover-pay-01"
    assert br2.json().get("resumed_existing") is True
    assert mock_start.call_count == 0

    db = SessionLocal()
    try:
        row = db.get(ShopOrder, oid)
        assert row is not None
        assert row.barion_payment_id == "recover-pay-01"
    finally:
        db.close()


def test_paid_attempt_without_orders_raises_and_ipn_non_2xx(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _barion_rest_env(monkeypatch)
    monkeypatch.setenv("BARION_IPN_SECRET", "ipn-secret-test-16b")

    db = SessionLocal()
    try:
        db.add(
            PaymentAttempt(
                checkout_group_id="missing-orders-group",
                barion_payment_id="paid-no-orders-01",
                payment_request_id="req-paid-no-orders-01",
                status="pending",
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    from fastapi import HTTPException

    from routers.payments_barion import sync_orders_payment_status_from_barion

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Succeeded"}):
        db = SessionLocal()
        try:
            with pytest.raises(HTTPException) as exc:
                sync_orders_payment_status_from_barion(db, "paid-no-orders-01")
            assert exc.value.status_code == 503
        finally:
            db.close()

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Succeeded"}):
        r = client.post(
            "/payments/barion/ipn?barion_ipn=ipn-secret-test-16b",
            json={"PaymentId": "paid-no-orders-01"},
        )
    assert r.status_code == 503
    assert r.json().get("ok") is not True


def test_paid_unknown_payment_id_does_not_mark_orders_paid(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _barion_rest_env(monkeypatch)
    monkeypatch.setenv("BARION_IPN_SECRET", "ipn-secret-test-16b")
    uid, pa, _pb = _seed_verified_user_and_products()
    r = client.post(
        "/orders",
        json=_checkout_order_body("Unknown Pay", [{"product_id": pa, "quantity": 1}]),
        headers=_auth_headers(uid),
    )
    oid = int(r.json()[0]["id"])

    from fastapi import HTTPException

    from routers.payments_barion import sync_orders_payment_status_from_barion

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Succeeded"}):
        db = SessionLocal()
        try:
            with pytest.raises(HTTPException) as exc:
                sync_orders_payment_status_from_barion(db, "totally-unknown-pay-99")
            assert exc.value.status_code == 503
        finally:
            db.close()

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Succeeded"}):
        ipn = client.post(
            "/payments/barion/ipn?barion_ipn=ipn-secret-test-16b",
            json={"PaymentId": "totally-unknown-pay-99"},
        )
    assert ipn.status_code == 503

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Succeeded"}):
        st = client.get(
            "/payments/barion/payment/totally-unknown-pay-99/state",
            headers=_auth_headers(uid),
        )
    assert st.status_code == 404

    db = SessionLocal()
    try:
        row = db.get(ShopOrder, oid)
        assert row is not None
        assert row.payment_status == "pending"
    finally:
        db.close()


def test_pending_unknown_payment_id_is_safe_no_op(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _barion_rest_env(monkeypatch)

    from routers.payments_barion import sync_orders_payment_status_from_barion

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Prepared"}):
        db = SessionLocal()
        try:
            shop, bst = sync_orders_payment_status_from_barion(db, "unknown-pending-01")
            assert shop == "pending"
            assert bst == "Prepared"
        finally:
            db.close()


def test_failed_unknown_payment_id_is_safe_no_op(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _barion_rest_env(monkeypatch)

    from routers.payments_barion import sync_orders_payment_status_from_barion

    with patch("routers.payments_barion.get_payment_state", return_value={"Status": "Failed"}):
        db = SessionLocal()
        try:
            shop, bst = sync_orders_payment_status_from_barion(db, "unknown-failed-01")
            assert shop == "failed"
            assert bst == "Failed"
        finally:
            db.close()
