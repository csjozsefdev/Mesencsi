"""Pytest fixtures for demo_backend integration tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("USER_JWT_SECRET", "demo-pytest-user-jwt-secret-not-for-production-xx")
os.environ.setdefault("GRAFI_PRODUCTION", "false")

from demo_backend.app import create_app
from demo_backend.incidents import clear_demo_incidents


@pytest.fixture
def client() -> TestClient:
    clear_demo_incidents()
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _reset_incidents() -> None:
    clear_demo_incidents()
    yield
    clear_demo_incidents()
