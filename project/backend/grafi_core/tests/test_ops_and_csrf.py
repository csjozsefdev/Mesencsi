import pytest

from grafi_core.ops.metrics import MetricsMiddleware, bucket_path, metrics_snapshot, reset_metrics_for_tests
from grafi_core.settings.cookie_names import CookieNames
from grafi_core.security.csrf import CsrfConfig, issue_csrf_token


def test_bucket_path_collapses_numeric_ids() -> None:
    assert bucket_path("/orders/123/items/456") == "/orders/{id}/items/{id}"


def test_metrics_snapshot_empty_after_reset() -> None:
    reset_metrics_for_tests()
    assert metrics_snapshot() == {"requests": []}


def test_csrf_issue_token_length() -> None:
    token = issue_csrf_token()
    assert len(token) >= 32


def test_csrf_config_cookie_names_override() -> None:
    names = CookieNames.mesencsi_defaults()
    cfg = CsrfConfig(cookie_names=names)
    assert cfg.cookie_names is not None
    assert cfg.cookie_names.csrf == "mesencsi_csrf"
