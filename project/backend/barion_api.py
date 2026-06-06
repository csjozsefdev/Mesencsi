"""Barion REST client — delegates to grafi_core with Mesencsi defaults."""

from __future__ import annotations

from typing import Any

from adapters.grafi_settings import mesencsi_core_settings
from grafi_core.payments import barion_client as _core

_barion_errors = _core._barion_errors  # used by payments_barion router


def barion_sandbox_mode() -> bool:
    return _core.barion_sandbox_mode(core_settings=mesencsi_core_settings())


def barion_api_base_url() -> str:
    return _core._api_base(core_settings=mesencsi_core_settings())


def barion_gateway_base_url() -> str:
    return _core._gateway_base(core_settings=mesencsi_core_settings())


def barion_backend_public_base() -> str:
    return _core.barion_backend_public_base()


def barion_frontend_landing_base() -> str:
    return _core.barion_frontend_landing_base()


def barion_pos_key() -> str:
    return _core.barion_pos_key()


def barion_ipn_secret() -> str:
    return _core.barion_ipn_secret()


def attach_barion_ipn_query(url: str) -> str:
    return _core.attach_barion_ipn_query(url)


def use_barion_rest_api() -> bool:
    return _core.use_barion_rest_api()


def start_payment_request(body: dict[str, Any]) -> dict[str, Any]:
    try:
        return _core.start_payment_request(body, core_settings=mesencsi_core_settings())
    except RuntimeError as exc:
        if str(exc) == "BARION_POS_KEY is missing":
            raise RuntimeError("BARION_POS_KEY hiányzik") from exc
        raise


def get_payment_state(payment_id: str) -> dict[str, Any]:
    try:
        return _core.get_payment_state(payment_id, core_settings=mesencsi_core_settings())
    except RuntimeError as exc:
        if str(exc) == "BARION_POS_KEY is missing":
            raise RuntimeError("BARION_POS_KEY hiányzik") from exc
        raise


def gateway_redirect_url(payment_id: str) -> str:
    return _core.gateway_redirect_url(payment_id, core_settings=mesencsi_core_settings())


def map_barion_status_to_payment_status(barion_status: str | None) -> str:
    return _core.map_barion_status_to_payment_status(barion_status)


def build_start_payment_body(
    *,
    payment_request_id: str,
    order_checkout_label: str,
    total_huf: int,
    redirect_url: str,
    callback_url: str | None,
    payer_hint_email: str | None,
) -> dict[str, Any]:
    try:
        return _core.build_start_payment_body(
            payment_request_id=payment_request_id,
            order_checkout_label=order_checkout_label,
            total_huf=total_huf,
            redirect_url=redirect_url,
            callback_url=callback_url,
            payer_hint_email=payer_hint_email,
            item_name="Webshop rendelés",
        )
    except ValueError as exc:
        if "BARION_PAYEE_EMAIL must be set" in str(exc):
            raise ValueError(
                "Állítsd be a BARION_PAYEE_EMAIL értéket (.env) — a Barion tranzakció Payee mezője "
                "a bolt regisztrált tulaj e-mailje."
            ) from exc
        raise


__all__ = [
    "_barion_errors",
    "attach_barion_ipn_query",
    "barion_backend_public_base",
    "barion_frontend_landing_base",
    "barion_ipn_secret",
    "barion_pos_key",
    "barion_sandbox_mode",
    "build_start_payment_body",
    "gateway_redirect_url",
    "get_payment_state",
    "map_barion_status_to_payment_status",
    "start_payment_request",
    "use_barion_rest_api",
]
