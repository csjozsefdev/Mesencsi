"""SMTP env key names — shared between email config and outbound transport (Milestone 2+)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SmtpSettings:
    host_env_key: str = "SMTP_HOST"
    port_env_key: str = "SMTP_PORT"
    user_env_key: str = "SMTP_USER"
    password_env_key: str = "SMTP_PASSWORD"
    from_env_key: str = "SMTP_FROM"
    use_tls_env_key: str = "SMTP_USE_TLS"
    default_port: int = 587
    default_use_tls: bool = True

    @property
    def env_keys(self) -> tuple[str, ...]:
        return (
            self.host_env_key,
            self.port_env_key,
            self.user_env_key,
            self.password_env_key,
            self.from_env_key,
            self.use_tls_env_key,
        )
