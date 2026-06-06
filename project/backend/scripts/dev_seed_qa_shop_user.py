#!/usr/bin/env python3
"""
LOCAL DEV ONLY: create/reset a known shop user for manual QA.

Creates or updates:
  email:    qa_user@example.com
  password: Test1234!

It sets email_verified_at and ensures the user is active (not banned/deleted),
so login + /auth/me flows are not blocked in local QA.

Refuses to run when:
  - MESENCSI_PRODUCTION=true
  - hosted deployment detected (RENDER / ENVIRONMENT)
  - database URL does not look local
"""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from database import DATABASE_URL, engine  # noqa: E402
from db_models import AppUser  # noqa: E402
from email_config import hosted_deployment  # noqa: E402
from password_utils import hash_password  # noqa: E402
from runtime_flags import mesencsi_production  # noqa: E402


QA_EMAIL = "qa_user@example.com"
QA_PASSWORD = "Test1234!"


def _assert_local_dev_only() -> None:
    if mesencsi_production():
        print("Refusing: MESENCSI_PRODUCTION is set.", file=sys.stderr)
        raise SystemExit(2)
    if hosted_deployment():
        print("Refusing: hosted deployment detected (RENDER / ENVIRONMENT).", file=sys.stderr)
        raise SystemExit(2)
    url = (DATABASE_URL or "").lower()
    if "sqlite" in url and ":memory:" not in url:
        return  # local sqlite file is ok
    if "localhost" in url or "127.0.0.1" in url:
        return
    if ("postgresql" in url or "postgres" in url) and ("localhost" not in url and "127.0.0.1" not in url):
        print(f"Refusing: database does not look local: {DATABASE_URL[:60]}...", file=sys.stderr)
        raise SystemExit(2)
    if not url:
        print("Refusing: DATABASE_URL is empty/unset.", file=sys.stderr)
        raise SystemExit(2)


def _safe_username_from_email(email: str) -> str:
    local = (email.split("@", 1)[0] or "qa").strip()
    u = re.sub(r"[^a-zA-Z0-9._-]+", "_", local).strip("._-") or "qa_user"
    return u[:64]


def main() -> int:
    _assert_local_dev_only()
    now = datetime.now(UTC)
    pwd_hash = hash_password(QA_PASSWORD)
    with Session(engine) as db:
        user = db.scalar(select(AppUser).where(func.lower(AppUser.email) == QA_EMAIL.lower()))
        if user is None:
            user = AppUser(
                username=_safe_username_from_email(QA_EMAIL),
                nickname=None,
                email=QA_EMAIL,
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
                deleted_at=None,
                last_login_at=None,
                email_verified_at=now,
                email_verification_token=None,
                email_verification_sent_at=None,
                password_reset_token_hash=None,
                password_reset_sent_at=None,
                password_reset_used_at=None,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"OK: QA shop user created (id={user.id}).")
        else:
            user.password_hash = pwd_hash
            user.is_active = True
            user.is_banned = False
            if user.is_deleted:
                user.is_deleted = False
                user.deleted_at = None
            user.email_verified_at = now
            user.email_verification_token = None
            user.email_verification_sent_at = None
            user.password_reset_token_hash = None
            user.password_reset_sent_at = None
            user.password_reset_used_at = None
            db.commit()
            print(f"OK: QA shop user reset (id={user.id}).")

    print(f"Credentials: {QA_EMAIL} / {QA_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

