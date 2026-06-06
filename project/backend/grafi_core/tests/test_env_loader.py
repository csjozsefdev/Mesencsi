from __future__ import annotations

from pathlib import Path

import pytest

from grafi_core.ops import env_loader


def test_env_loader_skips_under_pytest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_loader._loaded_by_dir.clear()
    env_file = tmp_path / ".env"
    env_file.write_text("SHOULD_NOT_LOAD=1\n", encoding="utf-8")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "grafi_core/tests/test_env_loader.py::test")
    loaded = env_loader.load_env_files(tmp_path)
    assert loaded == []
    assert "SHOULD_NOT_LOAD" not in __import__("os").environ


def test_env_loader_loads_env_file_when_not_pytest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_loader._loaded_by_dir.clear()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("GRAFI_LOADER_TEST_KEY=loaded\n", encoding="utf-8")
    loaded = env_loader.load_env_files(tmp_path)
    assert len(loaded) == 1
    assert "GRAFI_LOADER_TEST_KEY" in __import__("os").environ
    monkeypatch.delenv("GRAFI_LOADER_TEST_KEY", raising=False)
