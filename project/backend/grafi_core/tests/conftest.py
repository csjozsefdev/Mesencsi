"""Pytest fixtures for grafi_core unit tests."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _grafi_core_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_JWT_SECRET", "grafi-test-user-jwt-secret-not-for-production")
    monkeypatch.setenv("ADMIN_JWT_SECRET", "grafi-test-admin-jwt-secret-not-for-production")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("GRAFI_PRODUCTION", raising=False)
