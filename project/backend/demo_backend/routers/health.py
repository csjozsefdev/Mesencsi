"""Demo liveness and pytest-only error probe."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from demo_backend.settings import demo_core_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_live():
    settings = demo_core_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "production": settings.is_production(),
    }


@router.get("/health/raise-test", include_in_schema=False)
def health_raise_test():
    """Only active under pytest — verifies incident + request-id wiring."""
    if not demo_core_settings().is_pytest():
        raise HTTPException(status_code=404, detail="Not found")
    raise RuntimeError("demo pytest incident probe")
