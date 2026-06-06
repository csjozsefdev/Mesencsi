#!/usr/bin/env python3
"""
LOCAL DEV ONLY: remove one shop AppUser (users table) by email for registration/SMTP retest.

Does NOT touch admin/maintenance accounts (those are env-based, not in users).
Verification tokens live on the user row (email_verification_* columns) — no separate table.

Usage (backend folder, local DB only):
  python scripts/dev_delete_shop_user_by_email.py csjozsefdev@gmail.com
  python scripts/dev_delete_shop_user_by_email.py csjozsefdev@gmail.com --execute

Without --execute: preview only. Refuses hosted/production database URLs.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from database import DATABASE_URL, engine
from db_models import AppUser, LoginThrottle, PaymentAttempt, ShopOrder, UserCartItem
from email_config import hosted_deployment
from runtime_flags import mesencsi_production


def _assert_local_dev_only() -> None:
    if mesencsi_production():
        print("Refusing: MESENCSI_PRODUCTION is set.", file=sys.stderr)
        raise SystemExit(2)
    if hosted_deployment():
        print("Refusing: hosted deployment detected (RENDER / ENVIRONMENT).", file=sys.stderr)
        raise SystemExit(2)
    url = DATABASE_URL.lower()
    if "sqlite" in url and ":memory:" not in url:
        pass  # local sqlite file is ok
    elif "localhost" in url or "127.0.0.1" in url:
        pass
    elif "postgresql" in url or "postgres" in url:
        if "localhost" not in url and "127.0.0.1" not in url:
            print(f"Refusing: database does not look local: {DATABASE_URL[:60]}...", file=sys.stderr)
            raise SystemExit(2)
    else:
        print(f"Refusing: unrecognized local database URL: {DATABASE_URL[:80]}", file=sys.stderr)
        raise SystemExit(2)


def _preview(db: Session, email: str) -> AppUser | None:
    user = db.scalar(select(AppUser).where(func.lower(AppUser.email) == email.lower()))
    print(f"Target email: {email}")
    if user is None:
        print("No users row found — nothing to delete.")
        return None
    print(
        f"  users.id={user.id} username={user.username!r} "
        f"verified={user.email_verified_at is not None} "
        f"has_token={bool(user.email_verification_token)}"
    )
    orders = db.scalar(
        select(func.count()).select_from(ShopOrder).where(ShopOrder.user_id == user.id)
    )
    cart = db.scalar(
        select(func.count()).select_from(UserCartItem).where(UserCartItem.user_id == user.id)
    )
    throttle = db.get(LoginThrottle, email.lower())
    print(f"  orders={orders or 0} cart_items={cart or 0} login_throttle={'yes' if throttle else 'no'}")
    return user


def _payment_attempts_table_exists(db: Session) -> bool:
    row = db.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'payment_attempts'"
        )
    ).first()
    return row is not None


def _delete(db: Session, email: str, user_id: int) -> None:
    # 1) payment_attempts for this user's checkout groups (table may be absent on older local DBs)
    if _payment_attempts_table_exists(db):
        group_ids = db.scalars(
            select(ShopOrder.checkout_group_id)
            .where(ShopOrder.user_id == user_id)
            .where(ShopOrder.checkout_group_id.isnot(None))
            .distinct()
        ).all()
        if group_ids:
            db.execute(delete(PaymentAttempt).where(PaymentAttempt.checkout_group_id.in_(group_ids)))

    # 2) orders (FK restrict — must delete before user)
    db.execute(delete(ShopOrder).where(ShopOrder.user_id == user_id))

    # 3) login throttle by email
    db.execute(
        delete(LoginThrottle).where(
            func.lower(LoginThrottle.email_normalized) == email.lower()
        )
    )

    # 4) user (cart CASCADE; coupons/comments SET NULL)
    db.execute(delete(AppUser).where(AppUser.id == user_id))
    db.commit()
    print("OK — shop user and related rows removed.")


def main() -> int:
    _assert_local_dev_only()
    args = [a for a in sys.argv[1:] if a != "--execute"]
    execute = "--execute" in sys.argv[1:]
    if len(args) != 1:
        print(
            "Usage: python scripts/dev_delete_shop_user_by_email.py EMAIL [--execute]",
            file=sys.stderr,
        )
        return 2
    email = args[0].strip()
    if not email or "@" not in email:
        print("Invalid email.", file=sys.stderr)
        return 2

    with Session(engine) as db:
        user = _preview(db, email)
        if user is None:
            return 0
        if not execute:
            print("Preview only. Re-run with --execute to delete.")
            return 0
        _delete(db, email, user.id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
