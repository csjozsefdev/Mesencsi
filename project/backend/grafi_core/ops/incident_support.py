"""Request correlation and unhandled error persistence."""

from __future__ import annotations

import logging
import traceback
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import anyio
from fastapi import HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from grafi_core.logging.app_logging import request_id_cv

if TYPE_CHECKING:
    from fastapi import FastAPI

PersistIncidentFn = Callable[[Request, BaseException, str], None]
ApplySecurityHeadersFn = Callable[[Response], None]


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach request.state.request_id and echo X-Request-ID on the response."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_id_cv.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_cv.reset(token)


def build_unhandled_exception_handler(
    *,
    persist_incident: PersistIncidentFn,
    apply_security_headers: ApplySecurityHeadersFn,
    logger: logging.Logger,
    error_detail: str = "Internal server error",
) -> Callable[[Request, Exception], Any]:
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        await anyio.to_thread.run_sync(persist_incident, request, exc, tb_text)
        logger.exception("Unhandled error request_id=%s", getattr(request.state, "request_id", None))

        headers: dict[str, str] = {}
        if request_id := getattr(request.state, "request_id", None):
            headers["X-Request-ID"] = request_id

        response = JSONResponse(
            status_code=500,
            content={"detail": error_detail},
            headers=headers,
        )
        apply_security_headers(response)
        return response

    return unhandled_exception_handler


def register_incident_support(
    app: FastAPI,
    *,
    persist_incident: PersistIncidentFn,
    apply_security_headers: ApplySecurityHeadersFn,
    logger: logging.Logger | None = None,
    error_detail: str = "Internal server error",
) -> None:
    log = logger or logging.getLogger("grafi.incidents")
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(
        Exception,
        build_unhandled_exception_handler(
            persist_incident=persist_incident,
            apply_security_headers=apply_security_headers,
            logger=log,
            error_detail=error_detail,
        ),
    )
