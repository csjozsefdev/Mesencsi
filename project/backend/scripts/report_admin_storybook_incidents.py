#!/usr/bin/env python3
"""
Read-only diagnostic: show the real traceback behind unhandled 500s on the
storybook admin endpoints (e.g. "server error" when creating a new storybook).

The API never returns the real exception to clients (grafi_core/ops/incident_support.py
always responds with {"detail": "Internal server error"}) — the actual error_type,
message, and full traceback are persisted server-side in the `incidents` table
(db_models.py Incident) via adapters/incidents.py. This script reads that table.

Reuses the backend's own DB configuration (``database.SessionLocal``) — no
credentials are requested, read, or printed by this script. Performs
SELECT-only queries. Does not modify anything.

Usage (run from project/backend, with the same interpreter/venv the app uses):
    python scripts/report_admin_storybook_incidents.py
    python scripts/report_admin_storybook_incidents.py --limit 5
    python scripts/report_admin_storybook_incidents.py --path-like "%storybooks%"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from database import SessionLocal  # noqa: E402
from db_models import Incident  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=10, help="Max incidents to show (default 10)")
    p.add_argument(
        "--path-like",
        default="/admin/storybooks%",
        help="SQL LIKE pattern for request path (default: /admin/storybooks%%)",
    )
    args = p.parse_args()

    db = SessionLocal()
    try:
        rows = list(
            db.scalars(
                select(Incident)
                .where(Incident.path.like(args.path_like))
                .order_by(Incident.created_at.desc())
                .limit(args.limit)
            ).all()
        )

        if not rows:
            print(f"No incidents found for path LIKE {args.path_like!r}.")
            print("Either the error isn't hitting this path, or it never reached the unhandled-exception handler")
            print("(e.g. it could be a client-side JS error, or an HTTPException with its own status/detail).")
            return 0

        print(f"{len(rows)} incident(s) for path LIKE {args.path_like!r} (most recent first):")
        print("=" * 72)
        for r in rows:
            print(f"id={r.id}  created_at={r.created_at}  request_id={r.request_id}")
            print(f"{r.method} {r.path}  status_code={r.status_code}")
            print(f"error_type = {r.error_type}")
            print(f"message    = {r.message}")
            if r.traceback:
                print("traceback:")
                print(r.traceback)
            print("-" * 72)

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
