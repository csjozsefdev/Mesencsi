"""FastAPI application factory — wires grafi_core directly (no Mesencsi shims)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from demo_backend.incidents import persist_demo_incident
from demo_backend.rate_limits import limiter
from demo_backend.routers.auth_smoke import router as auth_smoke_router
from demo_backend.routers.health import router as health_router
from demo_backend.settings import demo_config_dir, demo_cookie_names, demo_core_settings
from grafi_core.auth.user_jwt import log_user_jwt_startup
from grafi_core.ops.env_loader import load_env_files
from grafi_core.ops.incident_support import register_incident_support
from grafi_core.security.csrf import CsrfConfig, CsrfMiddleware
from grafi_core.security.headers import apply_security_headers, register_security_headers


def _configure_logging(settings) -> None:
    if logging.root.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger(settings.logger_prefix).setLevel(logging.INFO)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = demo_core_settings()
    _configure_logging(settings)
    load_env_files(demo_config_dir(), logger_prefix=settings.logger_prefix)
    log_user_jwt_startup(core_settings=settings)
    yield


def create_app() -> FastAPI:
    settings = demo_core_settings()
    app = FastAPI(
        title="Grafi Core Demo",
        description="Minimal backend proving grafi_core works outside Mesencsi",
        lifespan=_lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    register_incident_support(
        app,
        persist_incident=persist_demo_incident,
        apply_security_headers=lambda response: apply_security_headers(response, core_settings=settings),
        logger=logging.getLogger(f"{settings.logger_prefix}.incidents"),
        error_detail="Internal server error",
    )

    app.include_router(health_router)
    app.include_router(auth_smoke_router)

    csrf_exempt = (
        "/health",
        "/auth/csrf",
        "/auth/smoke-login",
        "/auth/jwt-smoke",
    )
    app.add_middleware(
        CsrfMiddleware,
        config=CsrfConfig(
            cookie_names=demo_cookie_names(),
            exempt_prefixes=csrf_exempt,
        ),
    )
    register_security_headers(app, core_settings=settings)
    return app


app = create_app()
