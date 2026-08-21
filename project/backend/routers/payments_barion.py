"""Barion fizetés: sandbox/éles REST (Payment/Start, GetPaymentState), redirect visszatérés, stub mód POSKey nélkül."""

from __future__ import annotations

import logging
import os
import secrets
import uuid
from typing import Any, Literal

import anyio
BarionStartAction = Literal["new", "resume", "retry"]

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app_logging import get_request_id, log_event
from mesencsi_settings import mesencsi_core_settings
from barion_api import (
    _barion_errors,
    attach_barion_ipn_query,
    barion_api_base_url,
    barion_backend_public_base,
    barion_frontend_landing_base,
    barion_gateway_base_url,
    barion_ipn_secret,
    barion_pos_key,
    barion_sandbox_mode,
    build_start_payment_body,
    gateway_redirect_url,
    get_payment_state,
    map_barion_status_to_payment_status,
    start_payment_request,
    use_barion_rest_api,
)
from grafi_core.payments.barion_client import (
    BarionApiHttpError,
    _agent_debug_log,
    barion_error_codes_from_body,
    barion_start_debug_snapshot,
)
from database import SessionLocal, get_db
from db_models import AppUser, PaymentAttempt, ShopOrder
from dependencies import get_current_app_user, get_optional_app_user
from guest_checkout_tokens import guest_checkout_token_header_name, parse_guest_checkout_token
from payment_confirmation_email import schedule_payment_confirmation_after_paid_sync
from shipping_methods import checkout_group_grand_total_huf
from routers.cart import clear_user_cart
from runtime_flags import barion_payments_enabled, internal_barion_debug_authorized, mesencsi_production

router = APIRouter(prefix="/payments/barion", tags=["payments-barion"])
_log = logging.getLogger("mesencsi.payments")

# Client-safe messages — never attach raw exception text to HTTP responses.
_BARION_STATE_CLIENT_MSG = "A fizetés állapota jelenleg nem ellenőrizhető. Próbáld újra később."
_BARION_START_CLIENT_MSG = "A fizetés indítása sikertelen. Próbáld újra később."
_BARION_PAYMENTS_DISABLED_MSG = "A fizetés jelenleg nem elérhető. Próbáld újra később."


def _require_barion_payments_enabled() -> None:
    """``BARION_PAYMENTS_ENABLED=false``: checkout indítás és callback/IPN feldolgozás 503."""
    if not barion_payments_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_BARION_PAYMENTS_DISABLED_MSG,
        )


_BARION_UNAVAILABLE_CLIENT_MSG = "A fizetési szolgáltatás átmenetileg nem érhető el. Próbáld újra később."
_BARION_SHOP_DRAFT_CLIENT_MSG = (
    "A Barion bolt még nincs jóváhagyva (piszkozat állapot). "
    "Fejezd be a bolt regisztrációt és küldd jóváhagyásra a Barion teszt felületen, majd próbáld újra."
)

# Webshop `orders.payment_status` — csak backend Barion verify (GetPaymentState) után paid/failed/cancelled.
SHOP_PAYMENT_STATUSES: tuple[str, ...] = ("pending", "paid", "failed", "cancelled")
_TERMINAL_PAYMENT_STATUSES = frozenset({"paid", "failed", "cancelled"})


class BarionStartRequest(BaseModel):
    order_ids: list[int] = Field(..., min_length=1, description="Egy checkout sorai (orders.id).")
    description: str | None = Field(None, max_length=500)


class BarionStartResponse(BaseModel):
    mode: str
    payment_id: str
    redirect_url: str | None
    message: str
    order_ids: list[int]
    integration: Literal["stub", "barion"] = "stub"
    env: dict[str, Any]
    resumed_existing: bool = False


class BarionCallbackBody(BaseModel):
    """Manuális teszt / régi stub: egyszerű státusz beírás (nem a Barion IPN JSON-ja)."""

    payment_id: str = Field(..., min_length=8, max_length=128)
    status: str = Field(..., min_length=1, max_length=32, description="Succeeded | Failed | Canceled (stub, kis-nagybetű nem számít)")


class BarionPaymentStateResponse(BaseModel):
    payment_id: str
    payment_status: str
    barion_status: str | None = None


def _normalize_shop_payment_status(raw: str | None) -> str:
    s = (raw or "pending").strip().lower()
    return s if s in SHOP_PAYMENT_STATUSES else "pending"


def _payment_status_transition_allowed(current: str, new: str) -> bool:
    """Duplicate / visszaminősítés védelem (pl. késői IPN pendinggel ne írja felül a paid-et)."""
    if current == new:
        return False
    if current == "paid" and new != "paid":
        return False
    if current in _TERMINAL_PAYMENT_STATUSES and new == "pending":
        return False
    return True


def _apply_verified_payment_status_to_orders(rows: list[ShopOrder], new_status: str) -> int:
    new_status = _normalize_shop_payment_status(new_status)
    updated = 0
    for r in rows:
        cur = _normalize_shop_payment_status(r.payment_status)
        if not _payment_status_transition_allowed(cur, new_status):
            continue
        if cur != new_status:
            r.payment_status = new_status
            updated += 1
    return updated


def _clear_user_carts_after_confirmed_paid(db: Session, rows: list[ShopOrder]) -> None:
    """Server-side cart clears only after payment_status is confirmed paid."""
    user_ids = {int(r.user_id) for r in rows if r.user_id is not None}
    for uid in sorted(user_ids):
        clear_user_cart(db, uid)


def _map_callback_status(raw: str) -> str:
    s = raw.strip().lower()
    if s in ("succeeded", "success", "paid"):
        return "paid"
    if s in ("failed", "fail"):
        return "failed"
    if s in ("canceled", "cancelled", "cancel"):
        return "cancelled"
    return "pending"


def _checkout_group_key(rows: list[ShopOrder]) -> str:
    """Stable checkout group id for payment attempts (orders always have checkout_group_id in production)."""
    gid = (rows[0].checkout_group_id or "").strip()
    if gid:
        return gid
    ids = sorted(int(r.id) for r in rows)
    return "orders-" + "-".join(str(i) for i in ids)


def _get_active_pending_attempt(
    db: Session, checkout_group_id: str, *, for_update: bool = False
) -> PaymentAttempt | None:
    q = select(PaymentAttempt).where(
        PaymentAttempt.checkout_group_id == checkout_group_id,
        PaymentAttempt.is_active.is_(True),
        PaymentAttempt.status == "pending",
    )
    if for_update:
        q = q.with_for_update()
    return db.scalar(q)


def _deactivate_attempts_for_group(
    db: Session, checkout_group_id: str, *, except_attempt_id: int | None = None
) -> None:
    for att in db.scalars(
        select(PaymentAttempt).where(
            PaymentAttempt.checkout_group_id == checkout_group_id,
            PaymentAttempt.is_active.is_(True),
        )
    ):
        if except_attempt_id is not None and att.id == except_attempt_id:
            continue
        att.is_active = False


def _payment_attempt_for_barion_id(db: Session, payment_id: str) -> PaymentAttempt | None:
    pid = payment_id.strip()
    if not pid:
        return None
    return db.scalar(select(PaymentAttempt).where(PaymentAttempt.barion_payment_id == pid))


def _resolve_orders_for_barion_payment_id(db: Session, payment_id: str) -> list[ShopOrder]:
    """Orders by current barion_payment_id, or via PaymentAttempt history (orphan PaymentId after retry)."""
    pid = payment_id.strip()
    if not pid:
        return []
    rows = list(db.scalars(select(ShopOrder).where(ShopOrder.barion_payment_id == pid)).all())
    if rows:
        return rows
    attempt = _payment_attempt_for_barion_id(db, pid)
    if attempt is None:
        return []
    cg = (attempt.checkout_group_id or "").strip()
    if not cg:
        return []
    return list(db.scalars(select(ShopOrder).where(ShopOrder.checkout_group_id == cg)).all())


def _raise_if_unresolved_paid_barion_payment(
    *,
    payment_id: str,
    shop_status: str,
    barion_status: str | None,
    attempt: PaymentAttempt | None,
) -> None:
    """
    Barion GetPaymentState says paid but no local orders could be linked.

    IPN/return must not treat this as a successful sync (non-2xx). Unknown PaymentIds never update orders.
    """
    if shop_status != "paid":
        return
    pid_prefix = payment_id.strip()[:16]
    checkout_group_id = (attempt.checkout_group_id or "")[:64] if attempt else None
    base = {
        "request_id": get_request_id(),
        "payment_id": pid_prefix,
        "barion_status": barion_status,
        "shop_status": shop_status,
        "payment_attempt_found": attempt is not None,
        "checkout_group_id": checkout_group_id,
    }
    if attempt is not None:
        log_event(
            _log,
            logging.CRITICAL,
            "barion_payment_attempt_without_orders",
            **base,
        )
        log_event(
            _log,
            logging.CRITICAL,
            "barion_paid_payment_unresolved",
            **base,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Paid Barion payment could not be linked to orders (payment attempt without orders).",
        )
    log_event(
        _log,
        logging.ERROR,
        "barion_unknown_payment_id",
        **base,
    )
    log_event(
        _log,
        logging.ERROR,
        "barion_paid_payment_unresolved",
        **base,
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Paid Barion payment is not registered for this shop.",
    )


def _sync_payment_attempt_status(db: Session, payment_id: str, shop_status: str) -> None:
    attempt = db.scalar(select(PaymentAttempt).where(PaymentAttempt.barion_payment_id == payment_id))
    if attempt is None:
        return
    attempt.status = _normalize_shop_payment_status(shop_status)
    if attempt.status in _TERMINAL_PAYMENT_STATUSES:
        attempt.is_active = False


def _align_orders_to_payment_id(rows: list[ShopOrder], payment_id: str) -> None:
    for r in rows:
        r.barion_payment_id = payment_id
        if _normalize_shop_payment_status(r.payment_status) != "paid":
            r.payment_status = "pending"


def _barion_return_url() -> str:
    """Barion ``RedirectUrl`` — elsődlegesen ``BARION_RETURN_URL``, egyébként API return végpont."""
    u = (os.environ.get("BARION_RETURN_URL") or "").strip()
    return u if u else f"{barion_backend_public_base()}/payments/barion/return"


def _callback_url_if_configured() -> str | None:
    raw = (os.environ.get("BARION_CALLBACK_URL") or os.environ.get("BARION_IPN_URL") or "").strip()
    base = raw.rstrip("/") if raw else f"{barion_backend_public_base()}/payments/barion/ipn"
    return attach_barion_ipn_query(base)


def _frontend_landing_url() -> str:
    """Bolt UI redirect — delegál ``BARION_FRONTEND_LANDING_URL``-re, ha meg van adva."""
    return barion_frontend_landing_base()


def _barion_stub_payment_allowed() -> bool:
    """Preview / stub fizetés csak nem éles környezetben (``MESENCSI_PRODUCTION``)."""
    return not mesencsi_production()


def _ipn_secret_matches(candidate: str | None, secret: str) -> bool:
    if not secret or candidate is None:
        return False
    a = secret.encode("utf-8")
    b = candidate.strip().encode("utf-8")
    if len(a) != len(b):
        return False
    return secrets.compare_digest(a, b)


def _barion_ipn_request_authorized(request: Request) -> bool:
    """
    Barion IPN: a szolgáltatás nem küld dokumentált aláírást; a tényleges állapot a **GetPaymentState**
    (POSKey) hívással ellenőrizendő — ezt a szinkron futtatja. Kötelező védelem: ha ``BARION_IPN_SECRET`` be van
    állítva, a titkot a kérés ``barion_ipn`` query paraméterében (a Payment/Start ``CallbackUrl`` részeként,
    ``attach_barion_ipn_query`` automatikusan hozzáadja) vagy ``X-Barion-Ipn-Secret`` / ``Authorization: Bearer``
    fejlécben kell küldeni. ``MESENCSI_PRODUCTION=true`` mellett titok nélkül a végpont elutasítandó.
    """
    secret = barion_ipn_secret()
    if not secret:
        return not mesencsi_production()
    if _ipn_secret_matches(request.query_params.get("barion_ipn"), secret):
        return True
    if _ipn_secret_matches(request.headers.get("X-Barion-Ipn-Secret"), secret):
        return True
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        if _ipn_secret_matches(auth[7:].strip(), secret):
            return True
    return False


def _barion_manual_callback_allowed(request: Request) -> bool:
    """
    Manuális ``POST /payments/barion/callback``: fejlesztői módban engedélyezett;
    élesben csak ``X-Internal-Debug`` + ``MESENCSI_INTERNAL_DEBUG_SECRET`` egyezés esetén (alapból ki).
    """
    if not mesencsi_production():
        return True
    return internal_barion_debug_authorized(request.headers.get("X-Internal-Debug"))


def sync_orders_payment_status_from_barion(db: Session, payment_id: str) -> tuple[str, str | None]:
    """Barion GetPaymentState → PostgreSQL ``orders.payment_status`` (egyetlen hiteles verify útvonal REST módban)."""
    if not use_barion_rest_api():
        return "pending", None
    try:
        data = get_payment_state(payment_id)
    except Exception as e:
        _log.exception("barion_get_payment_state_failed payment_id=%s", payment_id[:16])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_BARION_STATE_CLIENT_MSG,
        ) from e
    bstatus = data.get("Status")
    bstatus_str = str(bstatus) if bstatus is not None else None
    shop = map_barion_status_to_payment_status(bstatus_str)
    attempt = _payment_attempt_for_barion_id(db, payment_id)
    rows = _resolve_orders_for_barion_payment_id(db, payment_id)
    if not rows:
        _raise_if_unresolved_paid_barion_payment(
            payment_id=payment_id,
            shop_status=shop,
            barion_status=bstatus_str,
            attempt=attempt,
        )
        return shop, bstatus_str
    rows_updated = _apply_verified_payment_status_to_orders(rows, shop)
    _sync_payment_attempt_status(db, payment_id, shop)
    if rows_updated > 0:
        db.commit()
        log_event(
            _log,
            logging.INFO,
            "barion_orders_synced",
            request_id=get_request_id(),
            payment_id=payment_id[:16],
            barion_status=bstatus_str,
            shop_status=shop,
            rows=len(rows),
            rows_updated=rows_updated,
        )
        if shop == "paid":
            _clear_user_carts_after_confirmed_paid(db, rows)
            try:
                schedule_payment_confirmation_after_paid_sync(payment_id, rows)
            except Exception:
                _log.exception(
                    "payment_confirmation_schedule_failed payment_id=%s",
                    payment_id[:16],
                )
    else:
        db.commit()
        log_event(
            _log,
            logging.INFO,
            "barion_orders_sync_idempotent",
            request_id=get_request_id(),
            payment_id=payment_id[:16],
            barion_status=bstatus_str,
            shop_status=shop,
            rows=len(rows),
        )
    return shop, bstatus_str


def sync_orders_payment_status_from_barion_isolated(payment_id: str) -> tuple[str, str | None]:
    """
    Run Barion sync in a dedicated DB session.

    This is safe to call from a thread (e.g. async IPN handler) to avoid blocking the event loop
    and to avoid using a request-scoped SQLAlchemy session across threads.
    """
    db = SessionLocal()
    try:
        out = sync_orders_payment_status_from_barion(db, payment_id)
        db.commit()
        return out
    finally:
        db.close()


def _load_orders_for_start(
    db: Session,
    order_ids: list[int],
    *,
    user_id: int | None = None,
    guest_checkout_group_id: str | None = None,
) -> list[ShopOrder]:
    """Load full checkout group; submitted IDs must match exactly."""
    submitted_ids = set(order_ids)
    if not submitted_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Legalább egy rendelési sort meg kell adni.",
        )
    if user_id is None and not guest_checkout_group_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bejelentkezés vagy vendég fizetési azonosító szükséges.",
        )
    rows = list(db.scalars(select(ShopOrder).where(ShopOrder.id.in_(submitted_ids))).all())
    if len(rows) != len(submitted_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Egy vagy több rendelési sor nem található.")
    for r in rows:
        if user_id is not None:
            if r.user_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ez a rendelés nem a te fiókodhoz tartozik.")
        elif r.user_id is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ehhez a rendeléshez be kell jelentkezned.")
    group_ids = {(r.checkout_group_id or "").strip() for r in rows}
    group_ids.discard("")
    if len(group_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A megadott sorok nem ugyanahhoz a kosár-checkout csoporthoz tartoznak.",
        )
    if not group_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rendelési sorokhoz nem tartozik checkout csoport.",
        )
    checkout_gid = next(iter(group_ids))
    if guest_checkout_group_id and checkout_gid != guest_checkout_group_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A vendég fizetési azonosító nem egyezik ezzel a rendeléssel.",
        )
    if user_id is not None:
        group_filter = (ShopOrder.user_id == user_id, ShopOrder.checkout_group_id == checkout_gid)
    else:
        group_filter = (ShopOrder.user_id.is_(None), ShopOrder.checkout_group_id == checkout_gid)
    all_rows = list(db.scalars(select(ShopOrder).where(*group_filter)).all())
    all_ids = {r.id for r in all_rows}
    if submitted_ids != all_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A fizetéshez a checkout összes rendelési sorát meg kell adni — részleges fizetés nem engedélyezett.",
        )
    for r in all_rows:
        if _normalize_shop_payment_status(r.payment_status) == "paid":
            log_event(
                _log,
                logging.WARNING,
                "barion_payment_start_blocked_paid",
                request_id=get_request_id(),
                order_id=r.id,
                user_id=user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ez a rendelés már fizetettnek van jelölve.",
            )
    return all_rows


def _collect_barion_payment_ids(rows: list[ShopOrder]) -> set[str]:
    return {(r.barion_payment_id or "").strip() for r in rows if (r.barion_payment_id or "").strip()}


def _classify_barion_start(rows: list[ShopOrder], *, user_id: int) -> tuple[BarionStartAction, str | None]:
    """
  - **resume**: pending + már van ``barion_payment_id`` → ne hívjunk új Payment/Start-ot.
  - **retry**: failed/cancelled (+ volt payment id) → új Barion session engedélyezett.
  - **new**: nincs aktív pending payment id.
    """
    statuses = {_normalize_shop_payment_status(r.payment_status) for r in rows}
    pids = _collect_barion_payment_ids(rows)

    if len(pids) > 1:
        log_event(
            _log,
            logging.ERROR,
            "barion_payment_start_blocked_inconsistent_ids",
            request_id=get_request_id(),
            user_id=user_id,
            payment_ids=",".join(sorted(pids))[:120],
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rendelési sorok között eltérő Barion fizetés azonosítók vannak — ügyfélszolgálat.",
        )

    allowed = {"pending", "failed", "cancelled"}
    if not statuses.issubset(allowed):
        log_event(
            _log,
            logging.WARNING,
            "barion_payment_start_blocked_unknown_status",
            request_id=get_request_id(),
            user_id=user_id,
            statuses=",".join(sorted(statuses)),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rendelés fizetési állapota nem indíthat új fizetést.",
        )

    if statuses == {"pending"} and pids:
        existing = next(iter(pids))
        log_event(
            _log,
            logging.INFO,
            "barion_payment_start_duplicate_resumed",
            request_id=get_request_id(),
            user_id=user_id,
            payment_id=existing[:16],
            order_count=len(rows),
        )
        return "resume", existing

    if statuses.issubset({"failed", "cancelled"}) and pids:
        log_event(
            _log,
            logging.INFO,
            "barion_payment_start_retry_after_terminal",
            request_id=get_request_id(),
            user_id=user_id,
            payment_id=next(iter(pids))[:16],
            statuses=",".join(sorted(statuses)),
        )
        return "retry", None

    if "pending" in statuses and (statuses & {"failed", "cancelled"}):
        log_event(
            _log,
            logging.WARNING,
            "barion_payment_start_blocked_mixed_status",
            request_id=get_request_id(),
            user_id=user_id,
            statuses=",".join(sorted(statuses)),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A checkout sorai eltérő fizetési állapotban vannak — új fizetés nem indítható.",
        )

    return "new", None


def _barion_start_response_resumed(
    *,
    payment_id: str,
    rows: list[ShopOrder],
    owner_user_id: int | None,
    payload: BarionStartRequest,
) -> BarionStartResponse:
    ids = [r.id for r in rows]
    env_user = {"user_id": owner_user_id, "resumed": True}
    if use_barion_rest_api():
        return BarionStartResponse(
            mode="barion_rest",
            payment_id=payment_id,
            redirect_url=gateway_redirect_url(payment_id),
            message="Meglévő függő Barion fizetés — folytasd a korábban indított fizetési oldalon.",
            order_ids=ids,
            integration="barion",
            env=env_user,
            resumed_existing=True,
        )
    sandbox = barion_sandbox_mode()
    base = (os.environ.get("PUBLIC_SITE_URL") or "http://127.0.0.1:8000").rstrip("/")
    fake_redirect = f"{base}/?payment=barion&pid={payment_id}&sandbox={str(sandbox).lower()}"
    return BarionStartResponse(
        mode="sandbox_stub" if sandbox else "live_pending",
        payment_id=payment_id,
        redirect_url=fake_redirect,
        message="Meglévő függő fizetés (stub) — ugyanaz a payment_id maradt érvényben.",
        order_ids=ids,
        integration="stub",
        env={**env_user, "description": payload.description},
        resumed_existing=True,
    )


@router.get("/status")
def barion_preview_status():
    """Nyilvános előnézet: Barion környezet (titkok nélkül). ``BARION_ENV`` dominál; ``BARION_SANDBOX`` csak visszafelé kompatibilis."""
    env_raw = (os.environ.get("BARION_ENV") or "").strip()
    sandbox = barion_sandbox_mode()
    return {
        "barion_env": env_raw or None,
        "sandbox": sandbox,
        "api_base_url": barion_api_base_url(),
        "gateway_base_url": barion_gateway_base_url(),
        "mesencsi_production": mesencsi_production(),
        "barion_payments_enabled": barion_payments_enabled(),
        "pos_key_configured": bool(barion_pos_key()),
        "rest_api_enabled": use_barion_rest_api(),
        "barion_ipn_secret_configured": bool(barion_ipn_secret()),
        "docs": "https://docs.barion.com/Payment-Start-v2",
        "callback_docs": "https://docs.barion.com/Callback_mechanism",
    }


def _resolve_barion_start_context(
    user: AppUser | None,
    guest_checkout_token: str | None,
) -> tuple[int | None, str | None]:
    """Returns (owner_user_id, guest_checkout_group_id)."""
    if user is not None:
        return user.id, None
    if not guest_checkout_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bejelentkezés vagy vendég fizetési azonosító szükséges.",
        )
    return None, parse_guest_checkout_token(guest_checkout_token)


@router.post("/start", response_model=BarionStartResponse)
def barion_start_payment(
    payload: BarionStartRequest,
    db: Session = Depends(get_db),
    user: AppUser | None = Depends(get_optional_app_user),
    guest_checkout_token: str | None = Header(default=None, alias=guest_checkout_token_header_name()),
):
    """
    1) Validate order rows (owner or guest token, single checkout group, not already paid).
    2a) **Barion mode** (BARION_POS_KEY set): Payment/Start, store PaymentId, redirect to gateway.
    2b) **Stub** (no POSKey): local preview id + redirect with query string (development).
    """
    _require_barion_payments_enabled()
    owner_user_id, guest_gid = _resolve_barion_start_context(user, guest_checkout_token)
    rows = _load_orders_for_start(
        db,
        payload.order_ids,
        user_id=owner_user_id,
        guest_checkout_group_id=guest_gid,
    )
    checkout_gid = _checkout_group_key(rows)
    start_action, existing_pid = _classify_barion_start(rows, user_id=owner_user_id or 0)

    # Retry after failed/cancelled: retire active attempts before resume/idempotency checks.
    if start_action == "retry":
        _deactivate_attempts_for_group(db, checkout_gid)
        db.commit()

    active_attempt = _get_active_pending_attempt(db, checkout_gid)
    if active_attempt and (active_attempt.barion_payment_id or "").strip():
        pid = active_attempt.barion_payment_id.strip()
        _align_orders_to_payment_id(rows, pid)
        db.commit()
        return _barion_start_response_resumed(
            payment_id=pid,
            rows=rows,
            owner_user_id=owner_user_id,
            payload=payload,
        )

    if start_action == "resume" and existing_pid:
        return _barion_start_response_resumed(
            payment_id=existing_pid,
            rows=rows,
            owner_user_id=owner_user_id,
            payload=payload,
        )

    ids = [r.id for r in rows]
    total_huf = checkout_group_grand_total_huf(rows)

    if use_barion_rest_api():
        locked = _get_active_pending_attempt(db, checkout_gid, for_update=True)
        if locked and (locked.barion_payment_id or "").strip():
            pid = locked.barion_payment_id.strip()
            _align_orders_to_payment_id(rows, pid)
            db.commit()
            return _barion_start_response_resumed(
                payment_id=pid,
                rows=rows,
                owner_user_id=owner_user_id,
                payload=payload,
            )

        if locked and (locked.payment_request_id or "").strip():
            payment_request_id = locked.payment_request_id.strip()
            attempt = locked
        else:
            payment_request_id = str(uuid.uuid4())
            attempt = PaymentAttempt(
                checkout_group_id=checkout_gid,
                payment_request_id=payment_request_id,
                status="pending",
                is_active=True,
            )
            db.add(attempt)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raced = _get_active_pending_attempt(db, checkout_gid)
                if raced and (raced.barion_payment_id or "").strip():
                    pid = raced.barion_payment_id.strip()
                    _align_orders_to_payment_id(rows, pid)
                    db.commit()
                    return _barion_start_response_resumed(
                        payment_id=pid,
                        rows=rows,
                        owner_user_id=owner_user_id,
                        payload=payload,
                    )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A fizetés már indítás alatt áll — próbáld újra pár másodperc múlva.",
                ) from None

        redirect_url = _barion_return_url()
        cb = _callback_url_if_configured()
        cancel_url = (os.environ.get("BARION_CANCEL_URL") or "").strip() or None
        payer = (rows[0].customer_email or "").strip() or None
        cs = mesencsi_core_settings()
        _agent_debug_log(
            "payments_barion.py:barion_start_payment",
            "barion_start_endpoint",
            {
                **barion_start_debug_snapshot(
                    core_settings=cs,
                    order_ids=ids,
                    total_huf=total_huf,
                    redirect_url=redirect_url,
                    callback_url=cb,
                    cancel_url=cancel_url,
                ),
                "start_action": start_action,
                "user_id": owner_user_id,
                "rest_api_enabled": True,
            },
            hypothesis_id="A",
        )
        try:
            body = build_start_payment_body(
                payment_request_id=payment_request_id,
                order_checkout_label=checkout_gid,
                total_huf=total_huf,
                redirect_url=redirect_url,
                callback_url=cb,
                payer_hint_email=payer,
            )
            data = start_payment_request(body)
        except ValueError as e:
            _log.error("barion_start_config_error user_id=%s err=%s", owner_user_id, e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_BARION_UNAVAILABLE_CLIENT_MSG,
            ) from e
        except BarionApiHttpError as e:
            barion_codes = barion_error_codes_from_body(e.body or "")
            # #region agent log
            _agent_debug_log(
                "payments_barion.py:barion_start_payment",
                "barion_start_http_error",
                {
                    "user_id": owner_user_id,
                    "barion_http_status": e.status_code,
                    "barion_error_codes": barion_codes[:5],
                },
                hypothesis_id="G",
            )
            # #endregion
            if "ShopIsInDraftState" in barion_codes:
                _log.error(
                    "barion_start_shop_draft user_id=%s barion_status=%s",
                    owner_user_id,
                    e.status_code,
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=_BARION_SHOP_DRAFT_CLIENT_MSG,
                ) from e
            _log.error(
                "barion_start_http_error user_id=%s status=%s barion_error_codes=%s body_prefix=%s",
                owner_user_id,
                e.status_code,
                barion_codes[:3],
                (e.body or "")[:200],
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=_BARION_START_CLIENT_MSG,
            ) from e
        except Exception as e:
            _log.exception("barion_start_failed user_id=%s", owner_user_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=_BARION_START_CLIENT_MSG,
            ) from e

        errs = _barion_errors(data)
        pid_raw = data.get("PaymentId")
        payment_id = str(pid_raw).strip() if pid_raw is not None else ""
        if errs or not payment_id:
            _log.error("barion_start_rejected errors=%s", errs)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Barion elutasította a fizetés indítást (nézd a szerver naplót).",
            )

        attempt = db.scalar(
            select(PaymentAttempt).where(PaymentAttempt.payment_request_id == payment_request_id)
        )
        if attempt is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Belső hiba: a fizetési kísérlet nem található.",
            )
        attempt.barion_payment_id = payment_id
        _deactivate_attempts_for_group(db, checkout_gid, except_attempt_id=attempt.id)
        attempt.is_active = True
        _align_orders_to_payment_id(rows, payment_id)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            try:
                rec = db.scalar(
                    select(PaymentAttempt).where(PaymentAttempt.payment_request_id == payment_request_id)
                )
                if rec is not None:
                    rec.barion_payment_id = payment_id
                    rec.is_active = True
                    db.commit()
            except Exception:
                db.rollback()
            log_event(
                _log,
                logging.CRITICAL,
                "barion_start_commit_failed",
                request_id=get_request_id(),
                checkout_group_id=checkout_gid[:32],
                payment_request_id=payment_request_id[:36],
                barion_payment_id_prefix=payment_id[:16],
                user_id=owner_user_id,
            )
            _log.exception("barion_start_orders_commit_failed user_id=%s", owner_user_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A fizetés a Barionnál elindult, de a rendelés mentése nem sikerült — próbáld újra ugyanazt a fizetést.",
            ) from e
        for r in rows:
            db.refresh(r)

        gw = gateway_redirect_url(payment_id)
        log_event(
            _log,
            logging.INFO,
            "barion_payment_started",
            request_id=get_request_id(),
            user_id=owner_user_id,
            payment_id=payment_id[:16],
            total_huf=total_huf,
            retry_after_terminal=start_action == "retry",
        )
        return BarionStartResponse(
            mode="barion_rest",
            payment_id=payment_id,
            redirect_url=gw,
            message="Átirányítás a Barion fizetési oldalra. Visszatéréskor a /payments/barion/return frissíti a státuszt.",
            order_ids=ids,
            integration="barion",
            env={"user_id": owner_user_id, "PaymentRequestId": payment_request_id},
            resumed_existing=False,
        )

    if not _barion_stub_payment_allowed():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Éles környezetben (MESENCSI_PRODUCTION) a Barion stub nem használható — állítsd be a BARION_POS_KEY-t.",
        )

    # --- Stub (POSKey nélkül), pl. pytest / helyi próba ---
    sandbox = barion_sandbox_mode()
    pos_id = (os.environ.get("BARION_POS_ID") or "").strip()
    if not sandbox and not pos_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Barion POS nincs konfigurálva (BARION_POS_ID), és BARION_POS_KEY sincs stub módhoz.",
        )

    pid = "preview-" + uuid.uuid4().hex[:12]
    stub_attempt = PaymentAttempt(
        checkout_group_id=checkout_gid,
        barion_payment_id=pid,
        payment_request_id=str(uuid.uuid4()),
        status="pending",
        is_active=True,
    )
    db.add(stub_attempt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _get_active_pending_attempt(db, checkout_gid)
        if existing and (existing.barion_payment_id or "").strip():
            pid = existing.barion_payment_id.strip()
            _align_orders_to_payment_id(rows, pid)
            db.commit()
            return _barion_start_response_resumed(
                payment_id=pid,
                rows=rows,
                owner_user_id=owner_user_id,
                payload=payload,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A fizetés már indítás alatt áll — próbáld újra pár másodperc múlva.",
        ) from None

    _deactivate_attempts_for_group(db, checkout_gid, except_attempt_id=stub_attempt.id)
    stub_attempt.is_active = True
    _align_orders_to_payment_id(rows, pid)
    db.commit()
    log_event(
        _log,
        logging.INFO,
        "barion_payment_started",
        request_id=get_request_id(),
        user_id=owner_user_id,
        payment_id=pid[:16],
        total_huf=total_huf,
        integration="stub",
        retry_after_terminal=start_action == "retry",
    )
    for r in rows:
        db.refresh(r)

    base = (os.environ.get("PUBLIC_SITE_URL") or "http://127.0.0.1:8000").rstrip("/")
    fake_redirect = f"{base}/?payment=barion&pid={pid}&sandbox={str(sandbox).lower()}"
    return BarionStartResponse(
        mode="sandbox_stub" if sandbox else "live_pending",
        payment_id=pid,
        redirect_url=fake_redirect,
        message="Stub: nincs BARION_POS_KEY — valós fizetéshez állítsd be a kulcsot és a BARION_PAYEE_EMAIL-t.",
        order_ids=ids,
        integration="stub",
        env={"user_id": owner_user_id, "description": payload.description},
        resumed_existing=False,
    )


@router.get("/return", name="barion_shop_return")
def barion_return_redirect(
    db: Session = Depends(get_db),
    paymentId: str | None = None,
    PaymentId: str | None = None,
):
    """
    **Lépés:** a vásárló befejezi vagy megszakítja a fizetést a Barion oldalon → a böngésző ide irányít (RedirectUrl).

    A Barion a ``paymentId`` query paramétert fűzi hozzá. Itt **GetPaymentState**-tel frissítjük a PostgreSQL ``orders`` sorokat,
    majd visszaküldjük a vásárlót a bolt frontendjére egyszerű queryvel.
    """
    pid = (paymentId or PaymentId or "").strip()
    front = _frontend_landing_url()
    if use_barion_rest_api() and pid:
        try:
            shop_status, _b = sync_orders_payment_status_from_barion(db, pid)
        except HTTPException:
            log_event(
                _log,
                logging.WARNING,
                "barion_return_sync_http_error",
                request_id=get_request_id(),
                payment_id=pid[:16],
            )
            return RedirectResponse(f"{front}/?payment=error", status_code=302)
        except Exception:
            _log.exception("barion_return_sync_failed")
            return RedirectResponse(f"{front}/?payment=error", status_code=302)
        return RedirectResponse(
            f"{front}/?payment=barion&result={shop_status}&pid={pid}",
            status_code=302,
        )
    return RedirectResponse(f"{front}/?payment=barion&result=unknown", status_code=302)


@router.get("/cancel", name="barion_shop_cancel")
def barion_cancel_redirect(
    db: Session = Depends(get_db),
    paymentId: str | None = None,
    PaymentId: str | None = None,
):
    """
    Opcionális „Mégse” landing. REST módban ugyanúgy **GetPaymentState** szinkron (nem feltételezünk cancelled-et).
    """
    pid = (paymentId or PaymentId or "").strip()
    front = _frontend_landing_url()
    if use_barion_rest_api() and pid:
        try:
            shop_status, _b = sync_orders_payment_status_from_barion(db, pid)
        except HTTPException:
            log_event(
                _log,
                logging.WARNING,
                "barion_cancel_sync_http_error",
                request_id=get_request_id(),
                payment_id=pid[:16],
            )
            return RedirectResponse(f"{front}/?payment=error", status_code=302)
        except Exception:
            _log.exception("barion_cancel_sync_failed")
            return RedirectResponse(f"{front}/?payment=error", status_code=302)
        return RedirectResponse(
            f"{front}/?payment=barion&result={shop_status}&pid={pid}",
            status_code=302,
        )
    return RedirectResponse(f"{front}/?payment=barion&result=cancelled", status_code=302)


@router.post("/ipn", status_code=200)
async def barion_ipn(request: Request, db: Session = Depends(get_db)):
    """
    **CallbackUrl** célja: a Barion POST-ol, ha változik a fizetés (Callback mechanizmus).

    **Validáció:** a Barion dokumentáció szerint az IPN nem aláírt; a tényleges állapot a **GetPaymentState**
    (POSKey) hívással ellenőrizendő — ezt a szinkron futtatja. Kötelező védelem: ha ``BARION_IPN_SECRET`` be van
    állítva, a titkot a kérés ``barion_ipn`` query paraméterében (a Payment/Start ``CallbackUrl`` részeként,
    ``attach_barion_ipn_query`` automatikusan hozzáadja) vagy ``X-Barion-Ipn-Secret`` / ``Authorization: Bearer``
    fejlécben kell küldeni. ``MESENCSI_PRODUCTION=true`` mellett titok nélkül a végpont **403**.
    """
    _require_barion_payments_enabled()
    if not _barion_ipn_request_authorized(request):
        log_event(_log, logging.WARNING, "barion_ipn_rejected_unauthorized", request_id=get_request_id())
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IPN hitelesítés sikertelen — állítsd be a BARION_IPN_SECRET értéket és a CallbackUrl-ben a barion_ipn paramétert (vagy proxy fejlécet).",
        )
    try:
        body = await request.json()
    except Exception:
        _log.warning("barion_ipn_non_json")
        return {"ok": True, "sync": "skipped"}
    if not isinstance(body, dict):
        return {"ok": True, "sync": "skipped"}
    pid = (body.get("PaymentId") or body.get("paymentId") or "").strip()
    if not pid or not use_barion_rest_api():
        log_event(_log, logging.INFO, "barion_ipn_skip", request_id=get_request_id(), has_payment_id=bool(pid))
        return {"ok": True, "sync": "skipped"}
    try:
        # Offload blocking Barion HTTP + DB work to a worker thread.
        await anyio.to_thread.run_sync(sync_orders_payment_status_from_barion_isolated, pid)
    except HTTPException:
        raise
    except Exception:
        _log.exception("barion_ipn_sync_failed payment_id=%s", pid[:16])
        log_event(
            _log,
            logging.ERROR,
            "barion_ipn_sync_failed",
            request_id=get_request_id(),
            payment_id=pid[:16],
            sync_failed=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment sync failed",
        ) from None
    return {"ok": True, "sync": "ok"}


@router.get("/payment/{payment_id}/state", response_model=BarionPaymentStateResponse)
def barion_get_payment_state(
    payment_id: str,
    db: Session = Depends(get_db),
    user: AppUser | None = Depends(get_optional_app_user),
    guest_checkout_token: str | None = Header(default=None, alias=guest_checkout_token_header_name()),
):
    """
    Poll Barion payment state and sync order rows. Authenticated users or guests with checkout token.
    """
    owner_user_id, guest_gid = _resolve_barion_start_context(user, guest_checkout_token if user is None else None)
    if user is None and not guest_checkout_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bejelentkezés vagy vendég fizetési azonosító szükséges.",
        )
    attempt = _payment_attempt_for_barion_id(db, payment_id)
    rows = _resolve_orders_for_barion_payment_id(db, payment_id)
    if not rows and attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This payment is not registered for this shop.",
        )
    if rows:
        if owner_user_id is not None:
            if any(r.user_id != owner_user_id for r in rows):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ez a fizetés nem a te fiókodhoz tartozik.")
        else:
            group_ids = {(r.checkout_group_id or "").strip() for r in rows}
            group_ids.discard("")
            if guest_gid and group_ids and guest_gid not in group_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="A vendég fizetési azonosító nem egyezik ezzel a fizetéssel.",
                )
            if any(r.user_id is not None for r in rows):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Ehhez a fizetéshez be kell jelentkezned.",
                )
    if not use_barion_rest_api():
        ps = rows[0].payment_status if rows else (attempt.status if attempt else "pending")
        return BarionPaymentStateResponse(payment_id=payment_id, payment_status=ps, barion_status=None)
    shop, bst = sync_orders_payment_status_from_barion(db, payment_id)
    return BarionPaymentStateResponse(payment_id=payment_id, payment_status=shop, barion_status=bst)


@router.post("/callback", status_code=204)
def barion_callback_stub(
    request: Request,
    payload: BarionCallbackBody,
    db: Session = Depends(get_db),
):
    """Kézi / fejlesztői stub (nem az éles Barion IPN). REST módban csak GetPaymentState szinkron — a body.status ignorálva."""
    _require_barion_payments_enabled()
    if not _barion_manual_callback_allowed(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ebben a környezetben ez a végpont nem használható.",
        )
    rows = _resolve_orders_for_barion_payment_id(db, payload.payment_id)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ismeretlen payment_id.")
    if use_barion_rest_api():
        sync_orders_payment_status_from_barion(db, payload.payment_id)
        return None
    pay_status = _map_callback_status(payload.status)
    rows_updated = _apply_verified_payment_status_to_orders(rows, pay_status)
    if rows_updated > 0:
        if pay_status == "paid":
            _clear_user_carts_after_confirmed_paid(db, rows)
        db.commit()
    log_event(
        _log,
        logging.INFO,
        "barion_callback_processed",
        request_id=get_request_id(),
        status=pay_status,
        rows_updated=rows_updated,
    )
    return None


@router.post("/webhook", status_code=204, deprecated=True)
def barion_webhook_alias(request: Request, payload: BarionCallbackBody, db: Session = Depends(get_db)):
    """Elavult alias — használd a ``POST /payments/barion/callback`` végpontot (ugyanaz a viselkedés)."""
    return barion_callback_stub(request, payload, db)
