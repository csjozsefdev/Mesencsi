"""Minimal shop-user auth repository protocol (Milestone 2 wiring target)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class UserAuthRecord(Protocol):
    id: int
    email: str
    password_hash: str
    email_verified_at: datetime | None
    is_banned: bool
    is_deleted: bool


@runtime_checkable
class UserAuthRepository(Protocol):
    def find_by_email(self, email: str) -> UserAuthRecord | None: ...

    def find_by_id(self, user_id: int) -> UserAuthRecord | None: ...
