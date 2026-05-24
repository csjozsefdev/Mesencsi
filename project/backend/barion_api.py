"""Barion REST v2 (sandbox / éles): Payment/Start + GetPaymentState — minimális kliens, env-ből."""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_log = logging.getLogger("mesencsi.barion_api")

DEFAULT_API_TEST = "https://api.test.barion.com"
DEFAULT_API_LIVE = "https://api.barion.com"
DEFAULT_GATEWAY_TEST = "https://secure.test.barion.com/Pay"
DEFAULT_GATEWAY_LIVE = "https://secure.barion.com/Pay"

_SANDBOX_ALIASES = frozenset(
    {"sandbox", "test", "staging", "dev", "development", "local", "debug"}
)
_PRODUCTION_ALIASES = frozenset({"production", "prod", "live", "release"})


def barion_sandbox_mode() -> bool:
    """
    Sandbox vs éles Barion API / gateway — elsődlegesen ``BARION_ENV``.

    - ``BARION_ENV`` (kis-nagybetű nem számít): sandbox / test / … → True; production / live / … → False.
    - Ha ``BARION_ENV`` üres: visszafelé kompatibilis ``BARION_SANDBOX`` (true/false/1/0).
    - Alapértelmezés: sandbox (teszt API).
    """
    raw = (os.environ.get("BARION_ENV") or "").strip().lower()
    if raw:
        if raw in _SANDBOX_ALIASES:
            return True
        if raw in _PRODUCTION_ALIASES:
            return False
        _log.warning("barion_env_unknown value=%r — defaulting to sandbox", raw)
        return True
    legacy = (os.environ.get("BARION_SANDBOX") or "true").strip().lower()
    return legacy in ("1", "true", "yes", "on")


def barion_backend_public_base() -> str:
    """A fizetés return / IPN URL-ek alapja — elsődlegesen ``BARION_BACKEND_PUBLIC_URL`` (Barion-blokk a .env-ben)."""
    return (
        (os.environ.get("BARION_BACKEND_PUBLIC_URL") or "").strip()
        or (os.environ.get("BACKEND_PUBLIC_URL") or "").strip()
        or (os.environ.get("PUBLIC_SITE_URL") or "").strip()
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def barion_frontend_landing_base() -> str:
    """Siker / hiba redirect a böngészőnek — elsődlegesen ``BARION_FRONTEND_LANDING_URL``."""
    return (
        (os.environ.get("BARION_FRONTEND_LANDING_URL") or "").strip()
        or (os.environ.get("PUBLIC_SITE_URL") or "").strip()
        or (os.environ.get("FRONTEND_BASE_URL") or "").strip()
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def barion_pos_key() -> str:
    return (os.environ.get("BARION_POS_KEY") or "").strip()


def barion_ipn_secret() -> str:
    """
    Opcionális közös titok a ``POST /payments/barion/ipn`` hívásokhoz.

    A Barion Callback mechanizmusa a fizetés változásakor POST-ol a ``CallbackUrl``-re (dokumentáció:
    https://docs.barion.com/Callback_mechanism ); a kérés törzsét önmagában nem írja alá a szolgáltatás.
    A hivatalos ellenőrzés a saját szerverről indított **GetPaymentState** (POSKey) — ezt továbbra is így tesszük.
    Emellett, ha ``BARION_IPN_SECRET`` be van állítva, a visszahívást csak akkor fogadjuk el, ha a titok
    megjelenik a kérés **query** paraméterében (``barion_ipn``, a CallbackUrl részeként, amit a Barion visszahív)
    vagy a ``X-Barion-Ipn-Secret`` / ``Authorization: Bearer`` fejlécben (pl. reverse proxy injektálja).
    """
    return (os.environ.get("BARION_IPN_SECRET") or "").strip()


def attach_barion_ipn_query(url: str) -> str:
    """Ha van ``BARION_IPN_SECRET``, a CallbackUrl-hez hozzáfűzi a ``barion_ipn`` query paramétert (Barion visszaadja a POST-on)."""
    secret = barion_ipn_secret()
    if not secret:
        return url.rstrip("/")
    u = url.rstrip("/")
    parts = urlparse(u)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "barion_ipn"]
    q.append(("barion_ipn", secret))
    new_query = urlencode(q)
    return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, new_query, parts.fragment))


def use_barion_rest_api() -> bool:
    """Ha van POSKey, a valós Barion API-t hívjuk (sandbox vagy éles URL). Stub módhoz hagyd üresen."""
    return bool(barion_pos_key())


def _api_base() -> str:
    sandbox = barion_sandbox_mode()
    override = (os.environ.get("BARION_API_BASE_URL") or "").strip()
    if override:
        return override.rstrip("/")
    return DEFAULT_API_TEST if sandbox else DEFAULT_API_LIVE


def _gateway_base() -> str:
    sandbox = barion_sandbox_mode()
    override = (os.environ.get("BARION_GATEWAY_URL") or "").strip()
    if override:
        return override.rstrip("/")
    return DEFAULT_GATEWAY_TEST if sandbox else DEFAULT_GATEWAY_LIVE


def _payee_email() -> str:
    return (os.environ.get("BARION_PAYEE_EMAIL") or "").strip()


def _http_post_json(url: str, payload: dict[str, Any], *, pos_key: str, timeout_s: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("x-pos-key", pos_key)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        _log.warning("barion_http_error status=%s body=%s", e.code, raw[:2000])
        raise
    return json.loads(raw) if raw else {}


def _http_get_json(url: str, *, pos_key: str, timeout_s: float = 30.0) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    req.add_header("x-pos-key", pos_key)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _barion_errors(data: dict[str, Any]) -> list[dict[str, Any]]:
    errs = data.get("Errors")
    return errs if isinstance(errs, list) else []


def start_payment_request(body: dict[str, Any]) -> dict[str, Any]:
    """POST /v2/Payment/Start — a body tartalmazza a POSKey-t (Barion dokumentáció szerint)."""
    pos_key = barion_pos_key()
    if not pos_key:
        raise RuntimeError("BARION_POS_KEY hiányzik")
    url = f"{_api_base()}/v2/Payment/Start"
    _log.info("barion_payment_start request_id=%s", body.get("PaymentRequestId"))
    data = _http_post_json(url, body, pos_key=pos_key)
    errs = _barion_errors(data)
    if errs:
        _log.error("barion_payment_start_errors %s", errs[:5])
    return data


def get_payment_state(payment_id: str) -> dict[str, Any]:
    """GET /v2/Payment/GetPaymentState?POSKey=…&PaymentId=…"""
    pos_key = barion_pos_key()
    if not pos_key:
        raise RuntimeError("BARION_POS_KEY hiányzik")
    q = urllib.parse.urlencode({"POSKey": pos_key, "PaymentId": payment_id})
    url = f"{_api_base()}/v2/Payment/GetPaymentState?{q}"
    _log.info("barion_get_payment_state payment_id=%s", payment_id[:8] + "…")
    return _http_get_json(url, pos_key=pos_key)


def gateway_redirect_url(payment_id: str) -> str:
    """Böngészős fizetés: Barion Smart Gateway (PHP klienshez hasonlóan ?id=)."""
    return f"{_gateway_base()}?id={urllib.parse.quote(payment_id, safe='')}"


def map_barion_status_to_payment_status(barion_status: str | None) -> str:
    """Barion PaymentStatus → orders.payment_status (egyszerű webshop értékek)."""
    if not barion_status:
        return "pending"
    s = barion_status.strip().lower()
    if s in ("succeeded", "partiallysucceeded"):
        return "paid"
    if s in ("canceled", "cancelled"):
        return "cancelled"
    if s in ("failed", "expired", "rejected"):
        return "failed"
    return "pending"


def build_start_payment_body(
    *,
    payment_request_id: str,
    order_checkout_label: str,
    total_huf: int,
    redirect_url: str,
    callback_url: str | None,
    payer_hint_email: str | None,
) -> dict[str, Any]:
    payee = _payee_email()
    if not payee:
        raise ValueError(
            "Állítsd be a BARION_PAYEE_EMAIL értéket (.env) — a Barion tranzakció Payee mezője a bolt regisztrált tulaj e-mailje."
        )
    tx_id = order_checkout_label[:99] if len(order_checkout_label) > 99 else order_checkout_label
    item_total = float(total_huf)
    body: dict[str, Any] = {
        "POSKey": barion_pos_key(),
        "PaymentType": "Immediate",
        "PaymentRequestId": payment_request_id,
        "PaymentWindow": (os.environ.get("BARION_PAYMENT_WINDOW") or "01:00:00").strip(),
        "GuestCheckout": True,
        "FundingSources": ["All"],
        "Locale": (os.environ.get("BARION_LOCALE") or "hu-HU").strip(),
        "Currency": (os.environ.get("BARION_CURRENCY") or "HUF").strip(),
        "RedirectUrl": redirect_url,
        "Transactions": [
            {
                "POSTransactionId": tx_id,
                "Payee": payee,
                "Total": item_total,
                "Items": [
                    {
                        "Name": "Webshop rendelés",
                        "Description": order_checkout_label[:200],
                        "Quantity": 1.0,
                        "Unit": "db",
                        "UnitPrice": item_total,
                        "ItemTotal": item_total,
                    }
                ],
            }
        ],
    }
    if callback_url:
        body["CallbackUrl"] = callback_url
    if payer_hint_email:
        body["PayerHint"] = payer_hint_email
    return body
