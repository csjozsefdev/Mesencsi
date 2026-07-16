"""bcrypt hash validation for startup and admin auth."""

from __future__ import annotations

from bcrypt_validation import is_valid_bcrypt_hash
from password_utils import hash_password


def test_valid_generated_hash() -> None:
    assert is_valid_bcrypt_hash(hash_password("secret-password-12"))


def test_rejects_placeholder_like_strings() -> None:
    assert not is_valid_bcrypt_hash("$2b$12$abcdefghijklmnopqrstuv0123456789012345678901234567890")
    assert not is_valid_bcrypt_hash("not-a-hash")
    assert not is_valid_bcrypt_hash("")
