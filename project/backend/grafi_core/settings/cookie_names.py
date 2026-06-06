"""HttpOnly session and CSRF cookie names — configurable per consuming app."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CookieNames:
    user_token: str = "grafi_user_token"
    admin_token: str = "grafi_admin_token"
    csrf: str = "grafi_csrf"

    @classmethod
    def mesencsi_defaults(cls) -> CookieNames:
        """Cookie names used by the Mesencsi sandbox (for Milestone 2 adapter mapping)."""
        return cls(
            user_token="mesencsi_user_token",
            admin_token="mesencsi_admin_token",
            csrf="mesencsi_csrf",
        )
