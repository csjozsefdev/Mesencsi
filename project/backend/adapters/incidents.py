"""Persist Mesencsi incidents to Postgres."""

from __future__ import annotations

import logging

from fastapi import Request

from database import SessionLocal
from db_models import Incident as IncidentRow

logger = logging.getLogger("mesencsi")


def persist_mesencsi_incident(request: Request, exc: BaseException, traceback_text: str) -> None:
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
    except Exception as persist_err:  # noqa: BLE001
        db.rollback()
        logger.error("Could not persist incident: %s", persist_err, exc_info=True)
    finally:
        db.close()
