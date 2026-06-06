"""JWT configuration — env key names and token type discriminators."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShopJwtErrorMessages:
    missing_secret: str = "Server cannot issue login tokens without {secret_env_key}."
    expired: str = "Access token expired. Please log in again."
    invalid: str = "Invalid access token."


@dataclass(frozen=True)
class AdminJwtErrorMessages:
    missing_secret: str = "Server cannot issue admin tokens without {secret_env_key}."
    expired: str = "Admin access token expired. Please log in again."
    invalid: str = "Invalid admin access token."


@dataclass(frozen=True)
class ShopJwtSettings:
    secret_env_key: str = "USER_JWT_SECRET"
    algorithm_env_key: str = "JWT_ALGORITHM"
    expire_minutes_env_key: str = "JWT_EXPIRE_MINUTES"
    expire_days_env_key: str = "USER_JWT_EXPIRE_DAYS"
    typ: str = "user"
    default_algorithm: str = "HS256"
    default_expire_days: int = 7
    error_messages: ShopJwtErrorMessages | None = None


@dataclass(frozen=True)
class AdminJwtSettings:
    secret_env_key: str = "ADMIN_JWT_SECRET"
    algorithm_env_key: str = "ADMIN_JWT_ALGORITHM"
    fallback_algorithm_env_key: str = "JWT_ALGORITHM"
    expire_hours_env_key: str = "ADMIN_JWT_EXPIRE_HOURS"
    expire_minutes_env_key: str = "ADMIN_JWT_EXPIRE_MINUTES"
    typ: str = "admin"
    default_algorithm: str = "HS256"
    default_expire_hours: float = 12.0
    allowed_roles: tuple[str, ...] = ("owner", "maintenance")
    error_messages: AdminJwtErrorMessages | None = None
