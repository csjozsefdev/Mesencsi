"""Idempotency-Key header validation."""

from __future__ import annotations

import pytest

from idempotency_key import IdempotencyKeyError, parse_idempotency_key_header


def test_valid_key_normalized() -> None:
    assert parse_idempotency_key_header("  checkout-abc-001  ") == "checkout-abc-001"


def test_blank_returns_none() -> None:
    assert parse_idempotency_key_header(None) is None
    assert parse_idempotency_key_header("   ") is None


def test_too_short_rejected() -> None:
    with pytest.raises(IdempotencyKeyError):
        parse_idempotency_key_header("short")


def test_invalid_chars_rejected() -> None:
    with pytest.raises(IdempotencyKeyError):
        parse_idempotency_key_header("checkout bad key!!")
