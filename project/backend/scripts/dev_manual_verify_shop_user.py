#!/usr/bin/env python3
"""
DEV / DEBUG ONLY: shop user „aktiválása” lokálisan.

- E-mail megerősítve (ugyanaz, mint sikeres /auth/verify-email után: token mezők null)
- is_active=True, is_banned=False (belépés / token végpontok)
- login_throttle törlése az e-mailhez (sikertelen belépés zárolás feloldása)

Opcionális: ha a fiók soft-delete (is_deleted), add hozzá a --restore flaget.

Használat (backend mappa):
  python scripts/dev_manual_verify_shop_user.py "te@email.com"
  python scripts/dev_manual_verify_shop_user.py "te@email.com" --restore

Nem módosít: jelszót.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

# Futtatás: `python scripts/dev_manual_verify_shop_user.py ...` a backend mappából
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import engine
from db_models import AppUser
from login_throttle import clear_login_throttle


def main() -> int:
    args = [a for a in sys.argv[1:] if a]
    restore = "--restore" in args
    args = [a for a in args if a != "--restore"]
    if len(args) != 1:
        print(
            'Használat: python scripts/dev_manual_verify_shop_user.py "email@pelda.hu" [--restore]',
            file=sys.stderr,
        )
        return 2
    email = args[0].strip()
    if not email or "@" not in email:
        print("Érvénytelen e-mail.", file=sys.stderr)
        return 2

    with Session(engine) as db:
        user = db.scalar(select(AppUser).where(func.lower(AppUser.email) == email.lower()))
        if user is None:
            print(f"Nincs ilyen user: {email}", file=sys.stderr)
            return 1
        if user.is_deleted and not restore:
            print(
                f"User soft-delete (is_deleted) — futtasd újra --restore flaggel: id={user.id}",
                file=sys.stderr,
            )
            return 1
        if user.is_deleted and restore:
            user.is_deleted = False
            user.deleted_at = None

        user.email_verified_at = datetime.now(UTC)
        user.email_verification_token = None
        user.email_verification_sent_at = None
        user.is_active = True
        user.is_banned = False
        db.commit()
        clear_login_throttle(db, user.email)

    print(
        f"OK — aktiválva: {email} (email verified, aktív, nincs tiltás, login throttle törölve"
        + (", soft-delete visszaállítva" if restore else "")
        + ").",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
