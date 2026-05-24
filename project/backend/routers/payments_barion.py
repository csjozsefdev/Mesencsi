"""Barion fizetés: sandbox/éles REST (Payment/Start, GetPaymentState), redirect visszatérés, stub mód POSKey nélkül."""

from __future__ import annotations

import logging
import os
import secrets
import uuid
from typing import Any, Literal

BarionStartAction = Literal["new", "resume", "retry"]

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_logging import get_request_id, log_event
from barion_api import (
    _barion_errors,
    attach_barion_ipn_query,
    barion_backend_public_base,
    barion_frontend_landing_base,
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
from database import get_db
from db_models import AppUser, ShopOrder
from dependencies import get_current_app_user
from payment_confirmation_email import schedule_payment_confirmation_after_paid_sync
from runtime_flags import internal_barion_debug_authorized, mesencsi_production

router = APIRouter(prefix="/payments/barion", tags=["payments-barion"])
_log = logging.getLogger("mesencsi.payments")

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


def _map_callback_status(raw: str) -> str:
    s = raw.strip().lower()
    if s in ("succeeded", "success", "paid"):
        return "paid"
    if s in ("failed", "fail"):
        return "failed"
    if s in ("canceled", "cancelled", "cancel"):
        return "cancelled"
    return "pending"


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
            detail=f"Barion GetPaymentState hiba: {e!s}",
        ) from e
    bstatus = data.get("Status")
    bstatus_str = str(bstatus) if bstatus is not None else None
    shop = map_barion_status_to_payment_status(bstatus_str)
    rows = list(db.scalars(select(ShopOrder).where(ShopOrder.barion_payment_id == payment_id)).all())
    if not rows:
        return shop, bstatus_str
    rows_updated = _apply_verified_payment_status_to_orders(rows, shop)
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
            try:
                schedule_payment_confirmation_after_paid_sync(payment_id, rows)
            except Exception:
                _log.exception(
                    "payment_confirmation_schedule_failed payment_id=%s",
                    payment_id[:16],
                )
    else:
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


def _load_orders_for_start(db: Session, user: AppUser, order_ids: list[int]) -> list[ShopOrder]:
    ids = list(dict.fromkeys(order_ids))
    rows = list(db.scalars(select(ShopOrder).where(ShopOrder.id.in_(ids))).all())
    if len(rows) != len(ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Egy vagy több rendelési sor nem található.")
    for r in rows:
        if r.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ez a rendelés nem a te fiókodhoz tartozik.")
        if _normalize_shop_payment_status(r.payment_status) == "paid":
            log_event(
                _log,
                logging.WARNING,
                "barion_payment_start_blocked_paid",
                request_id=get_request_id(),
                order_id=r.id,
                user_id=user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ez a rendelés már fizetettnek van jelölve.",
            )
    group_ids = {r.checkout_group_id for r in rows if r.checkout_group_id}
    if len(group_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A megadott sorok nem ugyanahhoz a kosár-checkout csoporthoz tartoznak.",
        )
    return rows


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
    user: AppUser,
    payload: BarionStartRequest,
) -> BarionStartResponse:
    ids = [r.id for r in rows]
    if use_barion_rest_api():
        return BarionStartResponse(
            mode="barion_rest",
            payment_id=payment_id,
            redirect_url=gateway_redirect_url(payment_id),
            message="Meglévő függő Barion fizetés — folytasd a korábban indított fizetési oldalon.",
            order_ids=ids,
            integration="barion",
            env={"user_id": user.id, "resumed": True},
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
        env={"user_id": user.id, "description": payload.description, "resumed": True},
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
        "mesencsi_production": mesencsi_production(),
        "pos_key_configured": bool(barion_pos_key()),
        "rest_api_enabled": use_barion_rest_api(),
        "barion_ipn_secret_configured": bool(barion_ipn_secret()),
        "docs": "https://docs.barion.com/Payment-Start-v2",
        "callback_docs": "https://docs.barion.com/Callback_mechanism",
    }


@router.post("/start", response_model=BarionStartResponse)
def barion_start_payment(
    payload: BarionStartRequest,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_app_user),
):
    """
    1) Validáljuk a rendelési sorokat (tulaj, egy checkout csoport, nincs már paid).
    2a) **Barion mód** (van ``BARION_POS_KEY``): összegből Payment/Start, ``PaymentId`` mentése, redirect a Barion gateway-re.
    2b) **Stub** (nincs POSKey): lokális ``preview-…`` id + visszairányítás a főoldal query stringgel (fejlesztői).
    """
    rows = _load_orders_for_start(db, user, payload.order_ids)
    start_action, existing_pid = _classify_barion_start(rows, user_id=user.id)
    if start_action == "resume" and existing_pid:
        return _barion_start_response_resumed(
            payment_id=existing_pid,
            rows=rows,
            user=user,
            payload=payload,
        )

    ids = [r.id for r in rows]
    total_huf = sum(int(r.total_price) for r in rows)
    checkout_gid = rows[0].checkout_group_id or ""

    if use_barion_rest_api():
        payment_request_id = str(uuid.uuid4())
        redirect_url = _barion_return_url()
        cb = _callback_url_if_configured()
        payer = (rows[0].customer_email or "").strip() or None
        try:
            body = build_start_payment_body(
                payment_request_id=payment_request_id,
                order_checkout_label=checkout_gid or f"orders-{','.join(str(i) for i in ids)}",
                total_huf=total_huf,
                redirect_url=redirect_url,
                callback_url=cb,
                payer_hint_email=payer,
            )
            data = start_payment_request(body)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
        except Exception as e:
            _log.exception("barion_start_failed user_id=%s", user.id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Barion Payment/Start sikertelen: {e!s}",
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

        for r in rows:
            r.payment_status = "pending"
            r.barion_payment_id = payment_id
        db.commit()
        for r in rows:
            db.refresh(r)

        gw = gateway_redirect_url(payment_id)
        log_event(
            _log,
            logging.INFO,
            "barion_payment_started",
            request_id=get_request_id(),
            user_id=user.id,
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
            env={"user_id": user.id, "PaymentRequestId": payment_request_id},
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
    for r in rows:
        r.payment_status = "pending"
        r.barion_payment_id = pid
    db.commit()
    log_event(
        _log,
        logging.INFO,
        "barion_payment_started",
        request_id=get_request_id(),
        user_id=user.id,
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
        env={"user_id": user.id, "description": payload.description},
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
            raise
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
            raise
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
        sync_orders_payment_status_from_barion(db, pid)
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
        return {"ok": True, "sync": "failed", "sync_failed": True}
    return {"ok": True, "sync": "ok"}


@router.get("/payment/{payment_id}/state", response_model=BarionPaymentStateResponse)
def barion_get_state_for_logged_in_user(
    payment_id: str,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_app_user),
):
    """
    Bejelentkezett vásárló: lekéri a Barion aktuális státuszát, **szinkronizálja** a saját rendelési sorait, és visszaadja az összefoglalót.
    """
    rows = list(db.scalars(select(ShopOrder).where(ShopOrder.barion_payment_id == payment_id)).all())
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen fizetés a rendelések között.")
    if any(r.user_id != user.id for r in rows):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ez a fizetés nem a te fiókodhoz tartozik.")
    if not use_barion_rest_api():
        return BarionPaymentStateResponse(payment_id=payment_id, payment_status=rows[0].payment_status, barion_status=None)
    shop, bst = sync_orders_payment_status_from_barion(db, payment_id)
    return BarionPaymentStateResponse(payment_id=payment_id, payment_status=shop, barion_status=bst)


@router.post("/callback", status_code=204)
def barion_callback_stub(
    request: Request,
    payload: BarionCallbackBody,
    db: Session = Depends(get_db),
):
    """Kézi / fejlesztői stub (nem az éles Barion IPN). REST módban csak GetPaymentState szinkron — a body.status ignorálva."""
    if not _barion_manual_callback_allowed(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ebben a környezetben ez a végpont nem használható.",
        )
    rows = list(db.scalars(select(ShopOrder).where(ShopOrder.barion_payment_id == payload.payment_id)).all())
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ismeretlen payment_id.")
    if use_barion_rest_api():
        sync_orders_payment_status_from_barion(db, payload.payment_id)
        return None
    pay_status = _map_callback_status(payload.status)
    rows_updated = _apply_verified_payment_status_to_orders(rows, pay_status)
    if rows_updated > 0:
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
