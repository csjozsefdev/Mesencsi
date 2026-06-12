"""Canonical shop user e-mail normalization."""

from __future__ import annotations


def normalize_shop_email(email: str) -> str:
    return str(email).strip().lower()
