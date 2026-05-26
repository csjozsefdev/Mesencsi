"""Local-only diagnostics — disabled on hosted deployments."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from email_config import hosted_deployment, smtp_config_diagnostic

router = APIRouter(prefix="/dev", tags=["dev-diagnostics"])


@router.get("/smtp-config")
def dev_smtp_config() -> dict[str, object]:
    """
    SMTP env snapshot for local debugging (no secrets).

    Not available when RENDER=true, ENVIRONMENT=staging|production, or MESENCSI_PRODUCTION.
    """
    if hosted_deployment():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return smtp_config_diagnostic()
