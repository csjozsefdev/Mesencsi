"""Vásárlói (shop user) auth: regisztráció, login JWT, email verify, jelszó reset."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from auth_limits import limiter
from database import get_db
from db_models import AppUser
from dependencies import get_current_app_user
from email_errors import EmailNotConfiguredError, EmailSendError
from email_outbound import _email_log_id, send_email_verification, send_password_reset_email
from login_throttle import assert_login_allowed, clear_login_throttle, record_login_failure
from models import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    UserAuthResponse,
    UserCreate,
    UserLogin,
    UserRead,
    UserRegisterResponse,
)
from password_utils import hash_password, verify_password
from policy_versions import PRIVACY_POLICY_VERSION, TERMS_VERSION
from user_email_verify import assign_verification_to_user, can_resend_verification, issue_verification_token, verify_user_by_token
from user_password_reset import (
    assign_reset_to_user,
    find_active_shop_user_by_email,
    find_user_for_reset_token,
    issue_reset_token,
    reset_token_invalid_reason,
)
from app_logging import get_request_id, log_event
from user_tokens import issue_user_access_token
from csrf import issue_csrf_token, set_csrf_cookie
from runtime_flags import auth_email_requires_working_smtp, mesencsi_production

router_auth = APIRouter(prefix="/auth", tags=["user-auth"])
_log = logging.getLogger("mesencsi.user_auth")


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


FORGOT_PASSWORD_GENERIC_MSG = (
    "Ha létezik ehhez az e-mail címhez fiók, néhány percen belül kapsz egy üzenetet a jelszó visszaállításához."
)

RESET_PASSWORD_INVALID_MSG = "Érvénytelen vagy lejárt jelszó-visszaállító link. Kérj új linket az „Elfelejtett jelszó” menüben."

RESET_PASSWORD_SUCCESS_MSG = "A jelszavad frissítve. Most már beléphetsz az új jelszóval."

CHANGE_PASSWORD_WRONG_CURRENT_MSG = "A jelenlegi jelszó nem helyes."
CHANGE_PASSWORD_SUCCESS_MSG = "A jelszó frissítve."

_REGISTER_EMAIL_FAIL_MSG = (
    "A regisztráció sikeres, de a visszaigazoló email küldése sikertelen. "
    "Ellenőrizd a szerver SMTP beállításait, vagy kérj új megerősítő levelet bejelentkezés után."
)

_REGISTER_EMAIL_DEV_NO_SMTP_MSG = (
    "A regisztráció sikeres. A backend/.env-ben nincs SMTP_HOST — a megerősítő link a szerver "
    "naplójában van (DEV). Állítsd be a Mailpit vagy szolgáltató SMTP változókat, majd indítsd újra az uvicorn-t."
)

_REGISTER_EMAIL_DEV_SMTP_UNREACHABLE_MSG = (
    "A regisztráció sikeres, de az SMTP szerver nem elérhető (pl. Mailpit nincs elindítva: "
    "docker compose up -d mailpit). Ellenőrizd a backend/.env SMTP_* értékeket és indítsd újra az uvicorn-t."
)

_REGISTER_EMAIL_DEV_LINK_IN_LOG_MSG = (
    "A regisztráció sikeres. A megerősítő e-mail nem ment ki SMTP-n (fejlesztői mód) — "
    "a megerősítő link a szerver termináljában van (keresd: LOCAL DEV AUTH EMAIL)."
)

_RESEND_EMAIL_DEV_NO_SMTP_MSG = (
    "Új megerősítő e-mail nem ment SMTP-n keresztül. A megerősítő link a szerver naplójában van (DEV)."
)


def _register_email_fail_message(*, verification_sent: bool, smtp_error: str | None = None) -> str | None:
    if verification_sent:
        return None
    if auth_email_requires_working_smtp():
        return _REGISTER_EMAIL_FAIL_MSG
    import os

    host = (os.environ.get("SMTP_HOST") or "").strip()
    if not host:
        return _REGISTER_EMAIL_DEV_NO_SMTP_MSG
    if smtp_error:
        return _REGISTER_EMAIL_DEV_SMTP_UNREACHABLE_MSG
    return _REGISTER_EMAIL_DEV_LINK_IN_LOG_MSG


@router_auth.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("8/minute")
def register_user(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    email = str(payload.email).strip()
    username = _allocate_username(db, email)
    accepted_at = datetime.now(UTC)

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
        terms_accepted_at=accepted_at,
        terms_version=TERMS_VERSION,
        privacy_acknowledged_at=accepted_at,
        privacy_version=PRIVACY_POLICY_VERSION,
    )
    token = issue_verification_token()
    _log.info("Verification token generated for new user recipient=%s", _email_log_id(email))
    assign_verification_to_user(db, row, token)
    db.add(row)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_duplicate_message(e)) from e
    except ProgrammingError as e:
        db.rollback()
        # Local DB can be behind migrations. In dev only, self-heal missing password reset columns so auth works.
        if not mesencsi_production() and "password_reset_token_hash" in str(e):
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token_hash VARCHAR(64)"))
                db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_sent_at TIMESTAMPTZ"))
                db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_used_at TIMESTAMPTZ"))
                db.add(row)
                db.commit()
            except Exception:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Adatbázis hiba — próbáld újra egy kicsit később.",
                ) from None
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Adatbázis hiba — próbáld újra egy kicsit később.",
            ) from None
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adatbázis hiba — próbáld újra egy kicsit később.",
        ) from None
    db.refresh(row)
    _log.info("Register successful — user id=%s recipient=%s", row.id, _email_log_id(row.email))

    verification_sent = False
    smtp_error_type: str | None = None
    try:
        verification_sent = send_email_verification(row.email, token)
    except (EmailNotConfiguredError, EmailSendError) as e:
        smtp_error_type = type(e).__name__
        _log.error(
            "Verification email failed after register — user id=%s recipient=%s error_type=%s error=%s",
            row.id,
            _email_log_id(row.email),
            type(e).__name__,
            e,
        )
        if auth_email_requires_working_smtp():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A regisztráció mentve, de a megerősítő e-mail küldése sikertelen. Próbáld újra később (bejelentkezés után új levél), vagy jelezd az ügyfélszolgálatnak.",
            ) from e
    except Exception as e:
        _log.error(
            "Verification email unexpected failure after register — user id=%s recipient=%s error_type=%s error=%s",
            row.id,
            _email_log_id(row.email),
            type(e).__name__,
            e,
            exc_info=True,
        )
        if auth_email_requires_working_smtp():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A regisztráció mentve, de a megerősítő e-mail küldése sikertelen. Próbáld újra később.",
            ) from e

    msg = _register_email_fail_message(
        verification_sent=verification_sent,
        smtp_error=smtp_error_type,
    )
    if not verification_sent:
        log_event(
            _log,
            logging.WARNING,
            "register_verification_email_not_sent",
            request_id=get_request_id(),
            user_id=row.id,
            recipient=_email_log_id(row.email),
        )
        if auth_email_requires_working_smtp():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A regisztráció mentve, de a megerősítő e-mail nem küldhető (SMTP). Próbáld újra később.",
            )

    return UserRegisterResponse(
        user=UserRead.model_validate(row),
        verification_email_sent=verification_sent,
        message=msg,
    )


@router_auth.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit("5/minute")
def forgot_password(request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Request password reset — always returns the same message (no email enumeration)."""
    email = str(payload.email).strip().lower()
    user = find_active_shop_user_by_email(db, email)
    if user is not None:
        plain_token = issue_reset_token()
        assign_reset_to_user(db, user, plain_token)
        db.commit()
        try:
            sent = send_password_reset_email(user.email, plain_token)
            if sent:
                log_event(
                    _log,
                    logging.INFO,
                    "password_reset_email_sent",
                    request_id=get_request_id(),
                    user_id=user.id,
                )
            else:
                log_event(
                    _log,
                    logging.WARNING,
                    "password_reset_email_dev_logged",
                    request_id=get_request_id(),
                    user_id=user.id,
                )
        except Exception as e:
            _log.error(
                "password_reset_email_failed — user id=%s error_type=%s",
                user.id,
                type(e).__name__,
            )
            if not auth_email_requires_working_smtp():
                from email_outbound import _log_dev_password_reset_link

                _log_dev_password_reset_link(to_email=user.email, token=plain_token)
    else:
        log_event(
            _log,
            logging.INFO,
            "password_reset_requested_unknown_email",
            request_id=get_request_id(),
        )
    return ForgotPasswordResponse(message=FORGOT_PASSWORD_GENERIC_MSG)


@router_auth.post("/change-password", response_model=ChangePasswordResponse)
@limiter.limit("10/minute")
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    user: AppUser = Depends(get_current_app_user),
    db: Session = Depends(get_db),
):
    """Bejelentkezett vásárló jelszó cseréje — jelenlegi jelszó ellenőrzéssel."""
    row = db.get(AppUser, user.id)
    if row is None or row.is_deleted or not row.is_active or row.is_banned:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ez a fiók nem elérhető.",
        )
    if not verify_password(payload.current_password, row.password_hash):
        log_event(
            _log,
            logging.INFO,
            "change_password_failed",
            request_id=get_request_id(),
            user_id=row.id,
            reason="bad_current_password",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CHANGE_PASSWORD_WRONG_CURRENT_MSG,
        )
    if verify_password(payload.password, row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Az új jelszó nem egyezhet a jelenlegivel.",
        )
    row.password_hash = hash_password(payload.password)
    row.password_reset_token_hash = None
    row.password_reset_sent_at = None
    row.password_reset_used_at = None
    db.commit()
    clear_login_throttle(db, row.email)
    log_event(
        _log,
        logging.INFO,
        "change_password_success",
        request_id=get_request_id(),
        user_id=row.id,
    )
    return ChangePasswordResponse(message=CHANGE_PASSWORD_SUCCESS_MSG)


@router_auth.post("/reset-password", response_model=ResetPasswordResponse)
@limiter.limit("10/minute")
def reset_password(request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Set a new password using a one-time reset token from email."""
    user = find_user_for_reset_token(db, payload.token)
    if user is None:
        log_event(
            _log,
            logging.INFO,
            "password_reset_failed",
            request_id=get_request_id(),
            reason="unknown_token",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=RESET_PASSWORD_INVALID_MSG)
    invalid = reset_token_invalid_reason(user)
    if invalid:
        log_event(
            _log,
            logging.INFO,
            "password_reset_failed",
            request_id=get_request_id(),
            user_id=user.id,
            reason=invalid,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=RESET_PASSWORD_INVALID_MSG)

    user.password_hash = hash_password(payload.password)
    user.password_reset_used_at = datetime.now(UTC)
    user.password_reset_token_hash = None
    user.password_reset_sent_at = None
    db.commit()
    clear_login_throttle(db, user.email)
    log_event(
        _log,
        logging.INFO,
        "password_reset_success",
        request_id=get_request_id(),
        user_id=user.id,
    )
    return ResetPasswordResponse(message=RESET_PASSWORD_SUCCESS_MSG)


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
    verification_sent = False
    smtp_error_type: str | None = None
    try:
        verification_sent = send_email_verification(user.email, token)
    except (EmailNotConfiguredError, EmailSendError) as e:
        smtp_error_type = type(e).__name__
        _log.error(
            "Verification email failed (resend) — user id=%s error_type=%s error=%s",
            user.id,
            type(e).__name__,
            e,
        )
        if auth_email_requires_working_smtp():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Nem sikerült elküldeni az e-mailt. Próbáld újra később vagy ellenőrizd az SMTP beállításokat.",
            ) from e
    except Exception as e:
        smtp_error_type = type(e).__name__
        _log.error(
            "Verification email unexpected failure (resend) — user id=%s error_type=%s error=%s",
            user.id,
            type(e).__name__,
            e,
            exc_info=True,
        )
        if auth_email_requires_working_smtp():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Nem sikerült elküldeni az e-mailt. Próbáld újra később vagy ellenőrizd az SMTP beállításokat.",
            ) from e
    if not verification_sent:
        if auth_email_requires_working_smtp():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Az e-mail küldés nincs konfigurálva (SMTP). Próbáld újra később.",
            )
        msg = _RESEND_EMAIL_DEV_NO_SMTP_MSG
        if smtp_error_type:
            msg = _REGISTER_EMAIL_DEV_SMTP_UNREACHABLE_MSG
        return {"ok": True, "verification_email_sent": False, "message": msg}
    return {"ok": True, "verification_email_sent": True}


@router_auth.post("/login", response_model=UserAuthResponse)
@limiter.limit("20/minute")
def login_user(
    request: Request,
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip()
    assert_login_allowed(db, email)
    projected = False
    try:
        row = db.scalar(select(AppUser).where(AppUser.email == email))
    except ProgrammingError as e:
        # Local DB can be behind migrations; avoid loading full AppUser row (selects all columns).
        projected = True
        # SQL errors abort the current transaction in Postgres; clear it before continuing.
        try:
            db.rollback()
        except Exception:
            pass
        row = db.execute(
            select(
                AppUser.id,
                AppUser.username,
                AppUser.nickname,
                AppUser.email,
                AppUser.password_hash,
                AppUser.phone,
                AppUser.shipping_address,
                AppUser.billing_address,
                AppUser.short_bio,
                AppUser.family_note,
                AppUser.profile_image_url,
                AppUser.is_active,
                AppUser.is_banned,
                AppUser.is_deleted,
                AppUser.last_login_at,
                AppUser.email_verified_at,
                AppUser.created_at,
                AppUser.updated_at,
            ).where(AppUser.email == email)
        ).first()
    if row is None:
        record_login_failure(db, email)
        log_event(_log, logging.INFO, "shop_login_failed", request_id=get_request_id(), reason="unknown_user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hibás e-mail cím vagy jelszó.",
        )
    if projected:
        (
            user_id,
            username,
            nickname,
            email_db,
            password_hash,
            phone,
            shipping_address,
            billing_address,
            short_bio,
            family_note,
            profile_image_url,
            is_active,
            is_banned,
            is_deleted,
            last_login_at,
            email_verified_at,
            created_at,
            updated_at,
        ) = row
    if (is_deleted if projected else row.is_deleted):
        log_event(_log, logging.INFO, "shop_login_failed", request_id=get_request_id(), reason="deleted_user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ez a fiók nem elérhető.",
        )
    if (is_banned if projected else row.is_banned):
        log_event(_log, logging.INFO, "shop_login_failed", request_id=get_request_id(), reason="banned_user")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ez a fiók tiltva van.",
        )
    if not (is_active if projected else row.is_active):
        log_event(_log, logging.INFO, "shop_login_failed", request_id=get_request_id(), reason="inactive_user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ez a fiók inaktív.",
        )
    if not verify_password(payload.password, password_hash if projected else row.password_hash):
        record_login_failure(db, email)
        log_event(_log, logging.INFO, "shop_login_failed", request_id=get_request_id(), reason="bad_password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hibás e-mail cím vagy jelszó.",
        )
    clear_login_throttle(db, email)
    if not projected:
        row.last_login_at = datetime.now(UTC)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Belépés sikeres, de nem sikerült menteni a munkamenetet. Próbáld újra.",
        ) from None
    if not projected:
        db.refresh(row)
        token = issue_user_access_token(row.id)
        user_out = UserRead.model_validate(row)
    else:
        token = issue_user_access_token(int(user_id))
        user_out = UserRead.model_validate(
            {
                "id": int(user_id),
                "username": str(username),
                "nickname": nickname,
                "email": str(email_db),
                "phone": phone,
                "shipping_address": shipping_address,
                "billing_address": billing_address,
                "short_bio": short_bio,
                "family_note": family_note,
                "profile_image_url": profile_image_url,
                "is_active": bool(is_active),
                "is_banned": bool(is_banned),
                "last_login_at": last_login_at,
                "email_verified_at": email_verified_at,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )
    response.set_cookie(
        "mesencsi_user_token",
        token,
        httponly=True,
        secure=(request.url.scheme == "https"),
        samesite="lax",
        path="/",
    )
    csrf_tok = issue_csrf_token()
    set_csrf_cookie(response, csrf_tok, secure=(request.url.scheme == "https"))
    return UserAuthResponse(access_token=token, user=user_out)


@router_auth.post("/logout")
def logout_user(response: Response):
    response.delete_cookie("mesencsi_user_token", path="/")
    return {"ok": True}


@router_auth.get("/csrf")
def csrf_token(request: Request, response: Response):
    tok = issue_csrf_token()
    set_csrf_cookie(response, tok, secure=(request.url.scheme == "https"))
    return {"csrf_token": tok}


@router_auth.get("/me", response_model=UserRead)
def auth_me(user: AppUser = Depends(get_current_app_user)):
    return user
