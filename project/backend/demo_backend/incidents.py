"""In-memory incident capture for the demo backend (no database)."""

from __future__ import annotations

from typing import Any

from fastapi import Request

_incidents: list[dict[str, Any]] = []


def persist_demo_incident(request: Request, exc: BaseException, traceback_text: str) -> None:
    request_id = getattr(request.state, "request_id", None)
    path = request.url.path
    if len(path) > 2048:
        path = path[:2048]
    _incidents.append(
        {
            "request_id": request_id,
            "method": request.method,
            "path": path,
            "error_type": type(exc).__name__,
            "message": str(exc)[:8000],
            "traceback": (traceback_text or "")[:50000],
        }
    )


def demo_incidents_snapshot() -> list[dict[str, Any]]:
    return list(_incidents)


def clear_demo_incidents() -> None:
    _incidents.clear()
