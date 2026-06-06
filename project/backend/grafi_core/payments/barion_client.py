"""Barion REST v2 client (sandbox / production): Payment/Start + GetPaymentState."""

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

from grafi_core.settings.core_settings import CoreSettings

_AGENT_DEBUG_LOG = "debug-bdbfb3.log"
_AGENT_DEBUG_SESSION = "bdbfb3"


class BarionApiHttpError(Exception):
    """Barion REST HTTP failure (status + response body for server logs only)."""

    def __init__(self, status_code: int, body: str, *, url: str) -> None:
        self.status_code = status_code
        self.body = body
        self.url = url
        super().__init__(f"Barion HTTP {status_code}")


DEFAULT_API_TEST = "https://api.test.barion.com"
DEFAULT_API_LIVE = "https://api.barion.com"
DEFAULT_GATEWAY_TEST = "https://secure.test.barion.com/Pay"
DEFAULT_GATEWAY_LIVE = "https://secure.barion.com/Pay"

_SANDBOX_ALIASES = frozenset({"sandbox", "test", "staging", "dev", "development", "local", "debug"})
_PRODUCTION_ALIASES = frozenset({"production", "prod", "live", "release"})


def _logger(core_settings: CoreSettings | None = None) -> logging.Logger:
    settings = core_settings or CoreSettings.from_env()
    return logging.getLogger(f"{settings.logger_prefix}.barion_api")


def barion_sandbox_mode(*, core_settings: CoreSettings | None = None) -> bool:
    log = _logger(core_settings)
    raw = (os.environ.get("BARION_ENV") or "").strip().lower()
    if raw:
        if raw in _SANDBOX_ALIASES:
            return True
        if raw in _PRODUCTION_ALIASES:
            return False
        log.warning("barion_env_unknown value=%r — defaulting to sandbox", raw)
        return True
    legacy = (os.environ.get("BARION_SANDBOX") or "true").strip().lower()
    return legacy in ("1", "true", "yes", "on")


def barion_backend_public_base() -> str:
    return (
        (os.environ.get("BARION_BACKEND_PUBLIC_URL") or "").strip()
        or (os.environ.get("BACKEND_PUBLIC_URL") or "").strip()
        or (os.environ.get("PUBLIC_SITE_URL") or "").strip()
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def barion_frontend_landing_base() -> str:
    return (
        (os.environ.get("BARION_FRONTEND_LANDING_URL") or "").strip()
        or (os.environ.get("PUBLIC_SITE_URL") or "").strip()
        or (os.environ.get("FRONTEND_BASE_URL") or "").strip()
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def barion_pos_key() -> str:
    return (os.environ.get("BARION_POS_KEY") or "").strip()


def barion_ipn_secret() -> str:
    return (os.environ.get("BARION_IPN_SECRET") or "").strip()


def attach_barion_ipn_query(url: str) -> str:
    secret = barion_ipn_secret()
    if not secret:
        return url.rstrip("/")
    cleaned = url.rstrip("/")
    parts = urlparse(cleaned)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "barion_ipn"]
    query.append(("barion_ipn", secret))
    return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, urlencode(query), parts.fragment))


def use_barion_rest_api() -> bool:
    return bool(barion_pos_key())


def _api_base(*, core_settings: CoreSettings | None = None) -> str:
    override = (os.environ.get("BARION_API_BASE_URL") or "").strip()
    if override:
        return override.rstrip("/")
    return DEFAULT_API_TEST if barion_sandbox_mode(core_settings=core_settings) else DEFAULT_API_LIVE


def _gateway_base(*, core_settings: CoreSettings | None = None) -> str:
    override = (os.environ.get("BARION_GATEWAY_URL") or "").strip()
    if override:
        return override.rstrip("/")
    return DEFAULT_GATEWAY_TEST if barion_sandbox_mode(core_settings=core_settings) else DEFAULT_GATEWAY_LIVE


def _payee_email() -> str:
    return (os.environ.get("BARION_PAYEE_EMAIL") or "").strip()


def _mask_payee_email(email: str) -> str:
    e = email.strip()
    if "@" not in e:
        return "(invalid)"
    local, domain = e.rsplit("@", 1)
    if not local:
        return f"***@{domain}"
    shown = local[:2] if len(local) > 2 else local[:1]
    return f"{shown}***@{domain}"


def _agent_debug_log(
    location: str,
    message: str,
    data: dict[str, Any],
    *,
    hypothesis_id: str = "",
    run_id: str = "pre-fix",
) -> None:
    # #region agent log
    try:
        from pathlib import Path
        import time

        log_path = Path(__file__).resolve().parents[2] / _AGENT_DEBUG_LOG
        entry = {
            "sessionId": _AGENT_DEBUG_SESSION,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
    # #endregion


def barion_start_debug_snapshot(
    *,
    core_settings: CoreSettings | None = None,
    order_ids: list[int] | None = None,
    total_huf: int | None = None,
    redirect_url: str | None = None,
    callback_url: str | None = None,
    cancel_url: str | None = None,
) -> dict[str, Any]:
    env_raw = (os.environ.get("BARION_ENV") or "").strip()
    sandbox = barion_sandbox_mode(core_settings=core_settings)
    payee = _payee_email()
    return {
        "order_ids": order_ids,
        "amount_huf": total_huf,
        "environment": env_raw or ("sandbox" if sandbox else "production"),
        "sandbox_mode": sandbox,
        "api_base_url": _api_base(core_settings=core_settings),
        "gateway_base_url": _gateway_base(core_settings=core_settings),
        "pos_key_exists": bool(barion_pos_key()),
        "payee_masked": _mask_payee_email(payee) if payee else None,
        "redirect_url": redirect_url,
        "callback_url": callback_url,
        "cancel_url": cancel_url,
    }


def _http_post_json(
    url: str,
    payload: dict[str, Any],
    *,
    pos_key: str,
    timeout_s: float = 30.0,
    core_settings: CoreSettings | None = None,
) -> dict[str, Any]:
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
        _logger(core_settings).warning("barion_http_error status=%s body=%s", e.code, raw[:2000])
        raise BarionApiHttpError(e.code, raw, url=url) from e
    return json.loads(raw) if raw else {}


def _http_get_json(
    url: str,
    *,
    pos_key: str,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    req.add_header("x-pos-key", pos_key)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _barion_errors(data: dict[str, Any]) -> list[dict[str, Any]]:
    errs = data.get("Errors")
    return errs if isinstance(errs, list) else []


def barion_error_codes_from_body(body: str) -> list[str]:
    """Parse Barion ``Errors[].ErrorCode`` from HTTP error JSON (no secrets)."""
    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return []
    errs = data.get("Errors")
    if not isinstance(errs, list):
        return []
    codes: list[str] = []
    for item in errs:
        if isinstance(item, dict):
            raw = item.get("ErrorCode")
            if isinstance(raw, str) and raw.strip():
                codes.append(raw.strip())
    return codes


def start_payment_request(body: dict[str, Any], *, core_settings: CoreSettings | None = None) -> dict[str, Any]:
    pos_key = barion_pos_key()
    if not pos_key:
        raise RuntimeError("BARION_POS_KEY is missing")
    url = f"{_api_base(core_settings=core_settings)}/v2/Payment/Start"
    _logger(core_settings).info("barion_payment_start request_id=%s", body.get("PaymentRequestId"))
    snap = barion_start_debug_snapshot(
        core_settings=core_settings,
        redirect_url=body.get("RedirectUrl"),
        callback_url=body.get("CallbackUrl"),
    )
    snap["payment_request_id"] = body.get("PaymentRequestId")
    _agent_debug_log(
        "barion_client.py:start_payment_request",
        "barion_payment_start_request",
        {**snap, "http_url": url},
        hypothesis_id="C",
    )
    try:
        data = _http_post_json(url, body, pos_key=pos_key, core_settings=core_settings)
    except BarionApiHttpError as exc:
        err_body = exc.body[:2000] if exc.body else ""
        _agent_debug_log(
            "barion_client.py:start_payment_request",
            "barion_payment_start_http_error",
            {
                **snap,
                "http_status": exc.status_code,
                "barion_error_body": err_body,
            },
            hypothesis_id="D",
        )
        log = _logger(core_settings)
        codes = barion_error_codes_from_body(exc.body)
        if exc.status_code == 401 and "ShopIsInDraftState" in codes:
            log.error(
                "barion_payment_start_shop_draft status=401 error_codes=%s",
                codes[:3],
            )
        elif exc.status_code == 401 and "AuthenticationFailed" in codes:
            log.error(
                "barion_payment_start_auth_failed status=401 hint=check BARION_POS_KEY matches BARION_ENV (sandbox key for api.test.barion.com)"
            )
        elif exc.status_code == 401:
            log.error(
                "barion_payment_start_http_401 status=401 error_codes=%s",
                codes[:3] or ["(unparsed)"],
            )
        raise
    errs = _barion_errors(data)
    if errs:
        _logger(core_settings).error("barion_payment_start_errors %s", errs[:5])
        _agent_debug_log(
            "barion_client.py:start_payment_request",
            "barion_payment_start_rejected",
            {**snap, "http_status": 200, "barion_errors": errs[:5]},
            hypothesis_id="E",
        )
    else:
        pid = data.get("PaymentId")
        _agent_debug_log(
            "barion_client.py:start_payment_request",
            "barion_payment_start_ok",
            {**snap, "http_status": 200, "payment_id_prefix": str(pid)[:16] if pid else None},
            hypothesis_id="F",
        )
    return data


def get_payment_state(payment_id: str, *, core_settings: CoreSettings | None = None) -> dict[str, Any]:
    pos_key = barion_pos_key()
    if not pos_key:
        raise RuntimeError("BARION_POS_KEY is missing")
    query = urllib.parse.urlencode({"POSKey": pos_key, "PaymentId": payment_id})
    url = f"{_api_base(core_settings=core_settings)}/v2/Payment/GetPaymentState?{query}"
    _logger(core_settings).info("barion_get_payment_state payment_id=%s", payment_id[:8] + "…")
    return _http_get_json(url, pos_key=pos_key)


def gateway_redirect_url(payment_id: str, *, core_settings: CoreSettings | None = None) -> str:
    return f"{_gateway_base(core_settings=core_settings)}?id={urllib.parse.quote(payment_id, safe='')}"


def map_barion_status_to_payment_status(barion_status: str | None) -> str:
    if not barion_status:
        return "pending"
    status = barion_status.strip().lower()
    if status in ("succeeded", "partiallysucceeded"):
        return "paid"
    if status in ("canceled", "cancelled"):
        return "cancelled"
    if status in ("failed", "expired", "rejected"):
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
    item_name: str = "Webshop order",
    locale: str | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    payee = _payee_email()
    if not payee:
        raise ValueError("BARION_PAYEE_EMAIL must be set — Barion Payee field requires the shop owner email.")
    tx_id = order_checkout_label[:99] if len(order_checkout_label) > 99 else order_checkout_label
    item_total = float(total_huf)
    body: dict[str, Any] = {
        "POSKey": barion_pos_key(),
        "PaymentType": "Immediate",
        "PaymentRequestId": payment_request_id,
        "PaymentWindow": (os.environ.get("BARION_PAYMENT_WINDOW") or "01:00:00").strip(),
        "GuestCheckout": True,
        "FundingSources": ["All"],
        "Locale": (locale or os.environ.get("BARION_LOCALE") or "hu-HU").strip(),
        "Currency": (currency or os.environ.get("BARION_CURRENCY") or "HUF").strip(),
        "RedirectUrl": redirect_url,
        "Transactions": [
            {
                "POSTransactionId": tx_id,
                "Payee": payee,
                "Total": item_total,
                "Items": [
                    {
                        "Name": item_name,
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
