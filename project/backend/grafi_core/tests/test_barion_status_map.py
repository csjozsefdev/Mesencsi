from grafi_core.payments.barion_client import map_barion_status_to_payment_status


def test_map_barion_status_succeeded() -> None:
    assert map_barion_status_to_payment_status("Succeeded") == "paid"


def test_map_barion_status_partially_succeeded() -> None:
    assert map_barion_status_to_payment_status("PartiallySucceeded") == "paid"


def test_map_barion_status_cancelled() -> None:
    assert map_barion_status_to_payment_status("Canceled") == "cancelled"
    assert map_barion_status_to_payment_status("cancelled") == "cancelled"


def test_map_barion_status_failed() -> None:
    assert map_barion_status_to_payment_status("Failed") == "failed"
    assert map_barion_status_to_payment_status("Expired") == "failed"


def test_map_barion_status_pending_and_empty() -> None:
    assert map_barion_status_to_payment_status("Prepared") == "pending"
    assert map_barion_status_to_payment_status(None) == "pending"
    assert map_barion_status_to_payment_status("") == "pending"
