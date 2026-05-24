#!/usr/bin/env python3
"""
Postgres smoke — külön futtatandó a default SQLite pytest suite-től.

Használat (PowerShell):
  $env:MESENCSI_POSTGRES_SMOKE_URL = "postgresql+psycopg://user:pass@localhost:5432/mesencsi_test"
  python scripts/postgres_smoke.py

Lásd: docs/postgres_smoke.md
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def main() -> int:
    url = (os.environ.get("MESENCSI_POSTGRES_SMOKE_URL") or "").strip()
    if not url:
        print("ERROR: állítsd be a MESENCSI_POSTGRES_SMOKE_URL env változót (postgresql+psycopg://…).")
        return 1

    env = os.environ.copy()
    env["MESENCSI_TEST_DATABASE_URL"] = url
    env.setdefault("USER_JWT_SECRET", "postgres-smoke-user-jwt-secret-32chars-min")
    env.setdefault("ADMIN_JWT_SECRET", "postgres-smoke-admin-jwt-secret-32chars-min")
    env.setdefault("MESENCSI_PRODUCTION", "false")

    print("→ alembic upgrade head …")
    subprocess.check_call(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND),
        env=env,
    )

    print("→ pytest tests/test_postgres_smoke.py …")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_postgres_smoke.py",
            "-q",
            "-m",
            "postgres",
        ],
        cwd=str(BACKEND),
        env=env,
    )

    print("OK: Postgres smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
