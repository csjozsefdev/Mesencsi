import logging

from grafi_core.logging.app_logging import log_event, safe_log_extra


def test_safe_log_extra_redacts_sensitive_keys() -> None:
    extra = safe_log_extra(password="secret", token="abc", smtp_password="x", note="ok")
    assert extra["password"] == "[REDACTED]"
    assert extra["token"] == "[REDACTED]"
    assert extra["smtp_password"] == "[REDACTED]"
    assert extra["note"] == "ok"


def test_safe_log_extra_truncates_long_strings() -> None:
    long_value = "a" * 250
    extra = safe_log_extra(message=long_value)
    assert len(extra["message"]) == 201
    assert extra["message"].endswith("…")


def test_log_event_format(caplog) -> None:
    logger = logging.getLogger("grafi.test.logging")
    with caplog.at_level(logging.INFO):
        log_event(logger, logging.INFO, "test_event", request_id="req-1", user_id=5)
    assert len(caplog.records) == 1
    message = caplog.records[0].message
    assert "event=test_event" in message
    assert "request_id=req-1" in message
    assert "user_id=5" in message
