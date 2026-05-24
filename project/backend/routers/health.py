"""Nyilvános és védett health végpontok."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import CurrentAdmin, require_role
from health_service import lightweight_health_payload, run_business_health

router = APIRouter(tags=["health"])


@router.get("/health")
def health_live():
    """Minimális liveness — nincs DB, gyors deploy / load balancer ellenőrzéshez."""
    return lightweight_health_payload()


@router.get("/health/business")
def health_business(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    """Mélyebb ellenőrzés — csak admin JWT; ne add ki külső monitornak (titkok nélkül sem)."""
    _ = _admin
    return run_business_health(db)
