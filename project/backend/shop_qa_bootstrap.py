"""Optional staging QA shop user — email-verified and active so checkout tests are not blocked."""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import SessionLocal
from db_models import AppUser
from email_config import hosted_deployment
from password_utils import hash_password, verify_password

_log = logging.getLogger("mesencsi.shop_qa_bootstrap")


def _qa_email() -> str:
    return (os.environ.get("QA_SHOP_EMAIL") or "").strip()


def _qa_password_raw() -> str:
    return (os.environ.get("QA_SHOP_PASSWORD") or "").strip()


def ensure_qa_shop_user() -> None:
    """
    When QA_SHOP_EMAIL and QA_SHOP_PASSWORD are set on a hosted deployment,
    ensure a shop AppUser exists with email_verified_at set and is_active=True.

    Password may be a bcrypt hash ($2…) or plain text (hashed on create / update).
    Admin panel users (OWNER_*/MAINTENANCE_*) are separate and do not use this path.
    """
    if not hosted_deployment():
        return
    email = _qa_email()
    password_raw = _qa_password_raw()
    if not email or not password_raw:
        return
    if "@" not in email:
        _log.warning("QA_SHOP_EMAIL is invalid — skipping QA shop bootstrap")
        return

    is_bcrypt = password_raw.startswith("$2")
    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(func.lower(AppUser.email) == email.lower()))
        now = datetime.now(UTC)
        if user is None:
            local = email.split("@", 1)[0].strip() or "qa"
            username = re.sub(r"[^a-zA-Z0-9._-]+", "_", local).strip("._-") or "qa"
            username = username[:64]
            pwd_hash = password_raw if is_bcrypt else hash_password(password_raw)
            user = AppUser(
                username=username,
                nickname=None,
                email=email,
                password_hash=pwd_hash,
                phone=None,
                shipping_address=None,
                billing_address=None,
                short_bio=None,
                family_note=None,
                profile_image_url=None,
                is_active=True,
                is_banned=False,
                is_deleted=False,
                email_verified_at=now,
                email_verification_token=None,
                email_verification_sent_at=None,
            )
            db.add(user)
            db.commit()
            _log.info("QA shop user created and email-verified — email=%s username=%s", email, username)
            return

        changed = False
        if user.email_verified_at is None:
            user.email_verified_at = now
            user.email_verification_token = None
            user.email_verification_sent_at = None
            changed = True
        if not user.is_active or user.is_banned or user.is_deleted:
            user.is_active = True
            user.is_banned = False
            if user.is_deleted:
                user.is_deleted = False
                user.deleted_at = None
            changed = True
        if is_bcrypt:
            if user.password_hash != password_raw:
                user.password_hash = password_raw
                changed = True
        elif not verify_password(password_raw, user.password_hash):
            user.password_hash = hash_password(password_raw)
            changed = True
        if changed:
            db.commit()
            _log.info("QA shop user updated (verified/active) — email=%s id=%s", email, user.id)
        else:
            _log.info("QA shop user already ready — email=%s id=%s", email, user.id)
