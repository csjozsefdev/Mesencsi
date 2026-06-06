"""CORS configuration — delegates to grafi_core with Mesencsi production flag."""

from adapters.grafi_settings import mesencsi_core_settings
from grafi_core.security.cors import (
    cors_origins_raw_env,
    parse_cors_origins_list,
    resolve_cors_allow_origins as _resolve_cors_allow_origins,
    validate_production_cors_origins,
)


def resolve_cors_allow_origins() -> list[str]:
    return _resolve_cors_allow_origins(mesencsi_core_settings())


__all__ = [
    "cors_origins_raw_env",
    "parse_cors_origins_list",
    "resolve_cors_allow_origins",
    "validate_production_cors_origins",
]
