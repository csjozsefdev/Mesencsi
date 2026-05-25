"""Request correlation + persist unhandled errors to ``incidents`` (Postgres)."""

from __future__ import annotations

import logging
import traceback
import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app_logging import request_id_cv
from database import SessionLocal
from db_models import Incident as IncidentRow
from security_headers import apply_security_headers

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("mesencsi")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach ``request.state.request_id`` and echo ``X-Request-ID`` on the response."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        tok = request_id_cv.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_cv.reset(tok)


def _persist_incident(
    request: Request,
    exc: BaseException,
    traceback_text: str,
) -> None:
    request_id = getattr(request.state, "request_id", None)
    path = request.url.path
    if len(path) > 2048:
        path = path[:2048]

    db = SessionLocal()
    try:
        row = IncidentRow(
            request_id=request_id[:64] if request_id else None,
            method=request.method[:16],
            path=path,
            status_code=500,
            error_type=type(exc).__name__[:255],
            message=str(exc)[:8000],
            traceback=traceback_text[:50000] if traceback_text else None,
        )
        db.add(row)
        db.commit()
    except Exception as persist_err:  # noqa: BLE001 — must not fail the error response path
        db.rollback()
        logger.error("Could not persist incident: %s", persist_err, exc_info=True)
    finally:
        db.close()


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    _persist_incident(request, exc, tb_text)
    logger.exception("Unhandled error request_id=%s", getattr(request.state, "request_id", None))

    headers: dict[str, str] = {}
    if rid := getattr(request.state, "request_id", None):
        headers["X-Request-ID"] = rid

    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=headers,
    )
    apply_security_headers(response)
    return response


def register_incident_support(app: FastAPI) -> None:
    """Register middleware + handlers. Call after ``FastAPI()`` is created."""
    app.add_middleware(RequestIdMiddleware)

    # Keep normal FastAPI behaviour for expected API errors (do not log those as incidents).
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
