"""Barion API/gateway host selection by BARION_ENV (no network)."""

from __future__ import annotations

import pytest

from grafi_core.payments.barion_client import (
    DEFAULT_API_LIVE,
    DEFAULT_API_TEST,
    DEFAULT_GATEWAY_LIVE,
    DEFAULT_GATEWAY_TEST,
    _api_base,
    _gateway_base,
)


@pytest.mark.parametrize(
    ("barion_env", "expected_api", "expected_gw"),
    [
        ("sandbox", DEFAULT_API_TEST, DEFAULT_GATEWAY_TEST),
        ("test", DEFAULT_API_TEST, DEFAULT_GATEWAY_TEST),
        ("production", DEFAULT_API_LIVE, DEFAULT_GATEWAY_LIVE),
        ("prod", DEFAULT_API_LIVE, DEFAULT_GATEWAY_LIVE),
        ("live", DEFAULT_API_LIVE, DEFAULT_GATEWAY_LIVE),
    ],
)
def test_barion_api_and_gateway_hosts(
    monkeypatch: pytest.MonkeyPatch,
    barion_env: str,
    expected_api: str,
    expected_gw: str,
) -> None:
    monkeypatch.setenv("BARION_ENV", barion_env)
    monkeypatch.delenv("BARION_API_BASE_URL", raising=False)
    monkeypatch.delenv("BARION_GATEWAY_URL", raising=False)
    assert _api_base() == expected_api
    assert _gateway_base() == expected_gw


def test_barion_api_base_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BARION_ENV", "sandbox")
    monkeypatch.setenv("BARION_API_BASE_URL", "https://api.test.barion.com")
    assert _api_base() == "https://api.test.barion.com"
