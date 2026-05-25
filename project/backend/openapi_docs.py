"""OpenAPI / Swagger UI exposure — disabled in production to avoid public schema leaks."""

from __future__ import annotations

from typing import Any

from runtime_flags import mesencsi_production


def fastapi_openapi_kwargs(*, production: bool | None = None) -> dict[str, Any]:
    """
    Extra ``FastAPI()`` keyword arguments.

    When production is active, ``docs_url``, ``redoc_url``, and ``openapi_url`` are
    set to ``None`` so ``/docs``, ``/redoc``, and ``/openapi.json`` are not registered.
    """
    prod = mesencsi_production() if production is None else production
    if prod:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}
