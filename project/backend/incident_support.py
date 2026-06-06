"""Request correlation + incident persistence — delegates to grafi_core."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from adapters.incidents import persist_mesencsi_incident
from grafi_core.ops.incident_support import RequestIdMiddleware, register_incident_support as _register
from security_headers import apply_security_headers

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("mesencsi")

__all__ = ["RequestIdMiddleware", "register_incident_support"]


def register_incident_support(app: FastAPI) -> None:
    _register(
        app,
        persist_incident=persist_mesencsi_incident,
        apply_security_headers=apply_security_headers,
        logger=logger,
    )
