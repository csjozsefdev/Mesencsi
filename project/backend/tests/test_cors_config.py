"""CORS origins: dev localhost, production explicit only, wildcard tiltás."""

from __future__ import annotations

import pytest

from cors_config import (
    parse_cors_origins_list,
    resolve_cors_allow_origins,
    validate_production_cors_origins,
)
from startup_config import StartupConfigError, run_startup_config_validation
from tests.test_startup_config import _fill_minimal_production_env


def test_dev_defaults_include_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MESENCSI_PRODUCTION", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    origins = resolve_cors_allow_origins()
    assert "http://127.0.0.1:8000" not in origins
    assert any("localhost" in o or "127.0.0.1" in o for o in origins)


def test_production_only_explicit_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://shop.example.com,https://www.shop.example.com")
    origins = resolve_cors_allow_origins()
    assert origins == ["https://shop.example.com", "https://www.shop.example.com"]


def test_production_empty_origins_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    assert resolve_cors_allow_origins() == []


def test_wildcard_rejected_in_production_validator() -> None:
    issues = validate_production_cors_origins(["*"])
    assert any("wildcard" in i.lower() for i in issues)


def test_wildcard_blocks_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    _fill_minimal_production_env(monkeypatch)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://shop.example.com,*")
    with pytest.raises(StartupConfigError) as exc:
        run_startup_config_validation()
    assert any("wildcard" in i.lower() for i in exc.value.issues)


def test_allowed_origins_alias_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESENCSI_PRODUCTION", "true")
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://legacy.example.com")
    assert resolve_cors_allow_origins() == ["https://legacy.example.com"]


def test_parse_cors_origins_list_trims() -> None:
    assert parse_cors_origins_list(" https://a.com , https://b.com ") == [
        "https://a.com",
        "https://b.com",
    ]
