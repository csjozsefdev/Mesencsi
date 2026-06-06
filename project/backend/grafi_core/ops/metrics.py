"""In-memory request metrics middleware and token-protected snapshot endpoint."""

from __future__ import annotations

import os
import time
from collections import Counter
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass(frozen=True)
class RequestMetric:
    method: str
    path: str
    status: int


_requests_total: Counter[RequestMetric] = Counter()
_requests_ms_total: Counter[RequestMetric] = Counter()


def bucket_path(path: str) -> str:
    parts = (path or "/").split("/")
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            out.append("{id}")
        else:
            out.append(part)
    return "/" + "/".join(out)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = int(getattr(response, "status_code", 200) or 200)
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            try:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                path = bucket_path(request.url.path)
                metric = RequestMetric(method=request.method.upper(), path=path, status=int(status_code))
                _requests_total[metric] += 1
                _requests_ms_total[metric] += elapsed_ms
            except Exception:
                pass


def metrics_snapshot() -> dict:
    items = []
    for metric, count in _requests_total.items():
        total_ms = int(_requests_ms_total.get(metric, 0))
        items.append(
            {
                "method": metric.method,
                "path": metric.path,
                "status": metric.status,
                "count": int(count),
                "total_ms": total_ms,
            }
        )
    items.sort(key=lambda row: (-row["count"], row["path"], row["method"], row["status"]))
    return {"requests": items}


def reset_metrics_for_tests() -> None:
    _requests_total.clear()
    _requests_ms_total.clear()


def require_metrics_token(request: Request) -> None:
    expected = (os.environ.get("METRICS_READ_TOKEN") or "").strip()
    if not expected:
        raise PermissionError("Metrics are disabled (set METRICS_READ_TOKEN).")
    got = (request.headers.get("X-Metrics-Token") or "").strip()
    if not got or got != expected:
        raise PermissionError("Missing or invalid X-Metrics-Token.")


def metrics_endpoint(request: Request) -> Response:
    try:
        require_metrics_token(request)
    except PermissionError as exc:
        return JSONResponse(status_code=403, content={"detail": str(exc)})
    return JSONResponse(status_code=200, content=metrics_snapshot())
