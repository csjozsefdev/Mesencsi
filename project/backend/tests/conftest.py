"""Pytest: teszt DB (SQLite memória) env beállítása minden import előtt + séma tesztenként."""

from __future__ import annotations

import os

os.environ.setdefault("MESENCSI_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("USER_JWT_SECRET", "pytest-user-jwt-secret-not-for-production-xx")
os.environ.setdefault("ADMIN_JWT_SECRET", "pytest-admin-jwt-secret-not-for-production-xx")

import pytest


@pytest.fixture(autouse=True)
def _clean_db_between_tests() -> None:
    import db_models  # noqa: F401 — regisztrálja az összes táblát a Base metadata alatt

    from database import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
