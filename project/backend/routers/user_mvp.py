"""Vásárlói (shop user) auth MVP: regisztráció, login JWT, profil, soft delete."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth_limits import limiter
from database import get_db
from db_models import AppUser, Coupon
from dependencies import get_current_app_user, require_email_verified_shop_user
from email_config import smtp_required_for_outbound
from email_errors import EmailNotConfiguredError, EmailSendError
from email_outbound import send_email_verification
from image_upload import delete_uploaded_file_by_url, save_uploaded_image
from login_throttle import assert_login_allowed, clear_login_throttle, record_login_failure
from models import (
    CouponPublicRead,
    UserAuthResponse,
    UserCreate,
    UserDeleteResponse,
    UserLogin,
    UserRead,
    UserRegisterResponse,
    UserUpdate,
)
from password_utils import hash_password, verify_password
from user_email_verify import assign_verification_to_user, can_resend_verification, issue_verification_token, verify_user_by_token
from app_logging import get_request_id, log_event
from user_tokens import issue_user_access_token
from shipping_address import (
    ShippingAddressValidationError,
    validate_hu_phone,
    validate_optional_profile_address_raw,
)

router_auth = APIRouter(prefix="/auth", tags=["user-auth"])
_log = logging.getLogger("mesencsi.user_auth")
router_users = APIRouter(prefix="/users", tags=["users"])


def _duplicate_message(exc: IntegrityError) -> str:
    err = str(exc.orig) if exc.orig else str(exc)
    low = err.lower()
    if "username" in low:
        return "Ez a felhasználónév már foglalt."
    if "email" in low:
        return "Ez az e-mail cím már regisztrálva van."
    return "Ez az adat ütközik egy már meglévő fiókkal."


def _allocate_username(db: Session, email: str) -> str:
    local = email.split("@", 1)[0].strip() or "user"
    local = re.sub(r"[^a-zA-Z0-9._-]+", "_", local).strip("._-") or "user"
    base = local[:64]
    cand = base
    n = 0
    while db.scalar(select(AppUser.id).where(AppUser.username == cand).limit(1)) is not None:
        n += 1
        suffix = f"_{n}"
        cand = (base[: max(1, 64 - len(suffix))] + suffix)[:64]
    return cand


_REGISTER_EMAIL_FAIL_MSG = (
    "A regisztráció sikeres, de a visszaigazoló email küldése sikertelen. "
    "Ellenőrizd a szerver SMTP beállításait, vagy kérj új megerősítő levelet bejelentkezés után."
)


@router_auth.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("8/minute")
def register_user(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    email = str(payload.email).strip()
    username = _allocate_username(db, email)

    row = AppUser(
        username=username,
        nickname=None,
        email=email,
        password_hash=hash_password(payload.password),
        phone=None,
        shipping_address=None,
        billing_address=None,
        short_bio=None,
        family_note=None,
        profile_image_url=None,
        is_active=True,
    )
    token = issue_verification_token()
    _log.info("Verification token generated for new user email=%s", email)
    assign_verification_to_user(db, row, token)
    db.add(row)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_duplicate_message(e)) from e
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adatbázis hiba — próbáld újra egy kicsit később.",
        ) from None
    db.refresh(row)
    _log.info("Register successful — user id=%s email=%s", row.id, row.email)

    verification_sent = False
    try:
        verification_sent = send_email_verification(row.email, token)
    except (EmailNotConfiguredError, EmailSendError) as e:
        _log.error(
            "Verification email failed after register — user id=%s email=%s error_type=%s error=%s",
            row.id,
            row.email,
            type(e).__name__,
            e,
        )
        if smtp_required_for_outbound():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A regisztráció mentve, de a megerősítő e-mail küldése sikertelen. Próbáld újra később (bejelentkezés után új levél), vagy jelezd az ügyfélszolgálatnak.",
            ) from e
    except Exception as e:
        _log.error(
            "Verification email unexpected failure after register — user id=%s email=%s error_type=%s error=%s",
            row.id,
            row.email,
            type(e).__name__,
            e,
            exc_info=True,
        )
        if smtp_required_for_outbound():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A regisztráció mentve, de a megerősítő e-mail küldése sikertelen. Próbáld újra később.",
            ) from e

    msg = None if verification_sent else _REGISTER_EMAIL_FAIL_MSG
    if not verification_sent:
        log_event(
            _log,
            logging.WARNING,
            "register_verification_email_not_sent",
            request_id=get_request_id(),
            user_id=row.id,
            email=row.email,
        )
        if smtp_required_for_outbound():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A regisztráció mentve, de a megerősítő e-mail nem küldhető (SMTP). Próbáld újra később.",
            )

    return UserRegisterResponse(
        user=UserRead.model_validate(row),
        verification_email_sent=verification_sent,
        message=msg,
    )


@router_auth.get("/verify-email")
@limiter.limit("30/minute")
def verify_email_public(request: Request, token: str, db: Session = Depends(get_db)):
    """Publikus link a regisztrációs e-mailből."""
    user = verify_user_by_token(db, token)
    if user is None:
        log_event(
            _log,
            logging.INFO,
            "email_verify_failed",
            request_id=get_request_id(),
            reason="invalid_or_expired_token",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Érvénytelen vagy lejárt megerősítő link. Kérhetsz újat a bejelentkezés után.",
        )
    return {"ok": True, "email": user.email}


@router_auth.post("/resend-verification")
@limiter.limit("3/minute")
def resend_verification_email(request: Request, user: AppUser = Depends(get_current_app_user), db: Session = Depends(get_db)):
    if user.email_verified_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Az e-mail cím már megerősítve van.")
    ok, wait_sec = can_resend_verification(user)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Kérlek várj még kb. {wait_sec} másodpercet az új levél előtt.",
        )
    token = issue_verification_token()
    assign_verification_to_user(db, user, token)
    db.commit()
    db.refresh(user)
    try:
        ok = send_email_verification(user.email, token)
    except (EmailNotConfiguredError, EmailSendError) as e:
        _log.error(
            "Verification email failed (resend) — user id=%s error_type=%s error=%s",
            user.id,
            type(e).__name__,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nem sikerült elküldeni az e-mailt. Próbáld újra később vagy ellenőrizd az SMTP beállításokat.",
        ) from e
    except Exception as e:
        _log.error(
            "Verification email unexpected failure (resend) — user id=%s error_type=%s error=%s",
            user.id,
            type(e).__name__,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nem sikerült elküldeni az e-mailt. Próbáld újra később vagy ellenőrizd az SMTP beállításokat.",
        ) from e
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Az e-mail küldés nincs konfigurálva (SMTP_HOST). Állítsd be a szervert, vagy fejlesztői módban nézd a naplót.",
        )
    return {"ok": True}


@router_auth.post("/login", response_model=UserAuthResponse)
@limiter.limit("20/minute")
def login_user(request: Request, payload: UserLogin, db: Session = Depends(get_db)):
    email = str(payload.email).strip()
    assert_login_allowed(db, email)
    row = db.scalar(select(AppUser).where(AppUser.email == email))
    if row is None:
        record_login_failure(db, email)
        log_event(_log, logging.INFO, "shop_login_failed", request_id=get_request_id(), reason="unknown_user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hibás e-mail cím vagy jelszó.",
        )
    if row.is_deleted:
        log_event(_log, logging.INFO, "shop_login_failed", request_id=get_request_id(), reason="deleted_user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ez a fiók nem elérhető.",
        )
    if row.is_banned:
        log_event(_log, logging.INFO, "shop_login_failed", request_id=get_request_id(), reason="banned_user")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ez a fiók tiltva van.",
        )
    if not row.is_active:
        log_event(_log, logging.INFO, "shop_login_failed", request_id=get_request_id(), reason="inactive_user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ez a fiók inaktív.",
        )
    if not verify_password(payload.password, row.password_hash):
        record_login_failure(db, email)
        log_event(_log, logging.INFO, "shop_login_failed", request_id=get_request_id(), reason="bad_password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hibás e-mail cím vagy jelszó.",
        )
    clear_login_throttle(db, email)
    row.last_login_at = datetime.now(UTC)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Belépés sikeres, de nem sikerült menteni a munkamenetet. Próbáld újra.",
        ) from None
    db.refresh(row)
    token = issue_user_access_token(row.id)
    return UserAuthResponse(access_token=token, user=UserRead.model_validate(row))


@router_auth.get("/me", response_model=UserRead)
def auth_me(user: AppUser = Depends(get_current_app_user)):
    return user


@router_users.get("/me/coupons", response_model=list[CouponPublicRead])
@limiter.limit("60/minute")
def list_my_active_coupons(
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_email_verified_shop_user),
):
    """Saját, aktív és nem lejárt, userhez rendelt kuponok (globális kódok nincsenek itt felsorolva)."""
    now = datetime.now(UTC)
    stmt = (
        select(Coupon)
        .where(
            Coupon.user_id == user.id,
            Coupon.is_active.is_(True),
            (Coupon.expires_at.is_(None)) | (Coupon.expires_at > now),
        )
        .order_by(Coupon.id.desc())
    )
    return list(db.scalars(stmt).all())


@router_users.get("/me", response_model=UserRead)
def users_me_alias(user: AppUser = Depends(get_current_app_user)):
    """Ugyanaz, mint ``GET /auth/me`` — alternatív útvonal a kliensek számára."""
    return user


@router_users.post("/me/avatar", response_model=UserRead)
@limiter.limit("20/minute")
async def upload_my_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_app_user),
):
    """Profilkép feltöltése — ``media/uploads/avatars`` (közös MIME + méret validáció)."""
    prev = user.profile_image_url
    try:
        url, _filename = await save_uploaded_image(file, subdir="avatars", filename_prefix=f"user-{int(user.id)}")
    except HTTPException:
        raise
    user.profile_image_url = url
    try:
        db.commit()
    except Exception:
        db.rollback()
        delete_uploaded_file_by_url(url)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nem sikerült elmenteni a profilképet. Próbáld újra.",
        ) from None
    db.refresh(user)
    if prev and str(prev).strip() and str(prev).strip() != url.strip():
        delete_uploaded_file_by_url(prev)
    return user


@router_users.patch("/me", response_model=UserRead)
def patch_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_app_user),
):
    data = payload.model_dump(exclude_unset=True)
    prev_email = user.email
    reverify_token: str | None = None
    if "username" in data and data["username"] is not None:
        user.username = str(data["username"]).strip()
    if "nickname" in data:
        raw = data.get("nickname")
        user.nickname = (str(raw).strip() if raw is not None else "") or None
    if "email" in data and data["email"] is not None:
        em = str(data["email"]).strip()
        if not em:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Az e-mail cím nem lehet üres.",
            )
        if em != prev_email:
            user.email = em
            reverify_token = issue_verification_token()
            assign_verification_to_user(db, user, reverify_token)
    if "short_bio" in data:
        sb = data.get("short_bio")
        user.short_bio = None if sb is None else (str(sb).strip() or None)
    if "family_note" in data:
        fn = data.get("family_note")
        user.family_note = None if fn is None else (str(fn).strip() or None)
    if "profile_image_url" in data:
        pu = data.get("profile_image_url")
        user.profile_image_url = None if pu is None else (str(pu).strip() or None)
    if "phone" in data:
        ph = data.get("phone")
        if ph is None:
            user.phone = None
        else:
            raw_ph = str(ph).strip()
            if not raw_ph:
                user.phone = None
            else:
                try:
                    user.phone = validate_hu_phone(raw_ph)
                except ShippingAddressValidationError as e:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=str(e),
                    ) from e
    if "shipping_address" in data:
        sa = data.get("shipping_address")
        try:
            user.shipping_address = validate_optional_profile_address_raw(
                None if sa is None else (str(sa).strip() or None)
            )
        except ShippingAddressValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e
    if "billing_address" in data:
        ba = data.get("billing_address")
        try:
            user.billing_address = validate_optional_profile_address_raw(
                None if ba is None else (str(ba).strip() or None)
            )
        except ShippingAddressValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_duplicate_message(e)) from e
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adatbázis hiba — próbáld újra egy kicsit később.",
        ) from None
    db.refresh(user)
    if reverify_token:
        try:
            send_email_verification(user.email, reverify_token)
        except Exception as e:
            _log.exception("Verification email failed after email change: %s", e)
    return user


@router_users.delete("/me", response_model=UserDeleteResponse)
def soft_delete_me(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_app_user),
):
    user.is_active = False
    user.is_deleted = True
    user.deleted_at = datetime.now(UTC)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nem sikerült a fiók deaktiválása. Próbáld újra.",
        ) from None
    db.refresh(user)
    return UserDeleteResponse(message="A fiók inaktiválva lett.", is_active=user.is_active)
