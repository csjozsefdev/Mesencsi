#!/usr/bin/env python3
"""Process pending email_outbox rows (cron-friendly).

Exit codes:
  0 — success (nothing to do, or all claimed rows sent)
  1 — retriable failures remain
  2 — dead-letter rows created in this batch
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from env_loader import load_backend_env

load_backend_env()

from database import SessionLocal
from email_outbox_worker import process_email_outbox_batch, requeue_dead_letters


def main() -> int:
    requeue = "--requeue-dead" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    limit = 50
    if args:
        try:
            limit = max(1, int(args[0]))
        except ValueError:
            print("Usage: process_email_outbox.py [limit] [--requeue-dead]", file=sys.stderr)
            return 1

    db = SessionLocal()
    try:
        if requeue:
            n = requeue_dead_letters(db, limit=limit)
            print(f"requeued={n}")
            return 0 if n >= 0 else 1

        result = process_email_outbox_batch(db, limit=limit)
        print(
            f"claimed={result.claimed} sent={result.sent} "
            f"failed={result.failed} dead={result.dead}"
        )
        if result.dead > 0:
            return 2
        if result.failed > 0:
            return 1
        return 0
    except Exception:
        print("email_outbox_batch_failed", file=sys.stderr)
        return 3
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
