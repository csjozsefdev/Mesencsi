"""
Opcionális Postgres smoke — csak MESENCSI_POSTGRES_SMOKE_URL / postgres_smoke.py mellett.

Default pytest (SQLite) ezt kihagyja.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import SessionLocal, engine
from mesencsi import app

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
    not (os.environ.get("MESENCSI_POSTGRES_SMOKE_URL") or os.environ.get("MESENCSI_TEST_DATABASE_URL", "")).startswith(
        "postgresql"
    ),
        reason="Postgres smoke only — set MESENCSI_POSTGRES_SMOKE_URL and run scripts/postgres_smoke.py",
    ),
]


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_postgres_engine_connects() -> None:
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_app_health_on_postgres(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "ok"


def test_basic_db_query_users_table() -> None:
    db = SessionLocal()
    try:
        n = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
        assert n is not None
    finally:
        db.close()
