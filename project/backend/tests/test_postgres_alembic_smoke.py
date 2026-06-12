"""PostgreSQL alembic upgrade head on a fresh database (integration)."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _pg_url(database: str) -> str:
    user = quote(os.getenv("POSTGRES_USER", "mesencsi"), safe="")
    password = quote(os.getenv("POSTGRES_PASSWORD", "mesencsi"), safe="")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{quote(database, safe='')}"


def test_alembic_upgrade_head_clean_postgres() -> None:
    admin_url = _pg_url("postgres")
    try:
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL not reachable for alembic smoke: {exc}")

    db_name = f"mesencsi_alembic_smoke_{uuid.uuid4().hex[:12]}"
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    try:
        env = os.environ.copy()
        env.pop("MESENCSI_TEST_DATABASE_URL", None)
        env["POSTGRES_DB"] = db_name
        env.setdefault("POSTGRES_USER", "mesencsi")
        env.setdefault("POSTGRES_PASSWORD", "mesencsi")
        env.setdefault("POSTGRES_HOST", "localhost")
        env.setdefault("POSTGRES_PORT", "5432")

        proc = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(BACKEND_DIR),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr or proc.stdout

        smoke_engine = create_engine(_pg_url(db_name))
        with smoke_engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert rev == "029"
    finally:
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{db_name}" WITH (FORCE)'))
