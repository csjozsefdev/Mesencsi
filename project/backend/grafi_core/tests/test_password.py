from grafi_core.auth.password import hash_password, verify_password


def test_password_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$2")
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_verify_password_empty_inputs() -> None:
    assert verify_password("", "hash") is False
    assert verify_password("plain", "") is False


def test_verify_password_invalid_hash() -> None:
    assert verify_password("plain", "not-a-bcrypt-hash") is False
