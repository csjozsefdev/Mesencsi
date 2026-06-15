"""Signed guest checkout tokens — authorize Barion start without a shop account."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException, status

GUEST_CHECKOUT_TOKEN_TTL_SEC = 7 * 24 * 3600
_TOKEN_HEADER = "X-Guest-Checkout-Token"
_INVALID_TOKEN_MSG = "Érvénytelen vagy hiányzó vendég fizetési azonosító."


def guest_checkout_token_header_name() -> str:
    return _TOKEN_HEADER


def _secret() -> bytes:
    raw = (os.getenv("USER_JWT_SECRET") or "").strip()
    if not raw:
        raise RuntimeError("USER_JWT_SECRET is required for guest checkout tokens")
    return raw.encode("utf-8")


def issue_guest_checkout_token(checkout_group_id: str) -> str:
    gid = (checkout_group_id or "").strip()
    if not gid:
        raise ValueError("checkout_group_id is required")
    payload = {
        "typ": "guest_checkout",
        "gid": gid,
        "exp": int(time.time()) + GUEST_CHECKOUT_TOKEN_TTL_SEC,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii").rstrip("=")
    sig = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def parse_guest_checkout_token(token: str) -> str:
    raw = (token or "").strip()
    if not raw or raw.count(".") != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_TOKEN_MSG,
        )
    body, sig = raw.split(".", 1)
    expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_TOKEN_MSG,
        )
    pad = "=" * (-len(body) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + pad))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_TOKEN_MSG,
        ) from exc
    if payload.get("typ") != "guest_checkout":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_TOKEN_MSG,
        )
    exp = int(payload.get("exp") or 0)
    if exp <= int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A vendég fizetési azonosító lejárt — függő fizetés esetén vedd fel a kapcsolatot az ügyfélszolgálattal.",
        )
    gid = (payload.get("gid") or "").strip()
    if not gid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_TOKEN_MSG,
        )
    return gid
