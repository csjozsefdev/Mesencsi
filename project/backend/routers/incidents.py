"""
Read recent error incidents from Postgres.

Writing incidents still happens in ``incident_support`` (on unhandled exceptions).
This router is only for *viewing* them during maintenance — not for “logging” per se.
"""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from db_models import Incident
from models import IncidentRead

router = APIRouter(prefix="/internal", tags=["internal"])


def _require_incidents_token(
    x_incidents_token: Annotated[str | None, Header(alias="X-Incidents-Token")] = None,
) -> None:
    expected = os.getenv("INCIDENTS_READ_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="A napló olvasása ki van kapcsolva. Az üzemeltetőnek be kell állítania az INCIDENTS_READ_TOKEN értéket.",
        )
    if not x_incidents_token or x_incidents_token != expected:
        raise HTTPException(
            status_code=401,
            detail="Hiányzik vagy hibás a napló-olvasási jelszó (X-Incidents-Token fejléc).",
        )


@router.get("/incidents", response_model=list[IncidentRead])
def list_incidents(
    db: Session = Depends(get_db),
    _: None = Depends(_require_incidents_token),
    limit: int = Query(50, ge=1, le=100),
) -> list[Incident]:
    """Latest incidents first. Send header ``X-Incidents-Token`` matching ``INCIDENTS_READ_TOKEN``."""
    stmt = select(Incident).order_by(Incident.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())
