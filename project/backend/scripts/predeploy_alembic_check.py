#!/usr/bin/env python3
"""Pre-deploy Alembic safety check — read-only; exits non-zero on unsafe legacy DB."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from env_loader import load_backend_env

load_backend_env()

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from database import DATABASE_URL


def main() -> int:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    print(f"alembic_heads: {', '.join(heads)}")

    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        current = ctx.get_current_revision()
        print(f"alembic_current: {current or '(empty)'}")

        insp = inspect(conn)
        tables = set(insp.get_table_names())
        if "orders" in tables and current in (None, "001", "002", "003", "004", "005", "006"):
            count = conn.execute(text("SELECT count(*) FROM orders")).scalar_one()
            if int(count) > 0:
                print(
                    "ERROR: Legacy database detected before revision 007 with existing orders rows. "
                    "Migration 007 deletes all orders when adding user_id. "
                    "Take a backup and plan a manual data migration before upgrading.",
                    file=sys.stderr,
                )
                return 2
    print("predeploy_alembic_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
