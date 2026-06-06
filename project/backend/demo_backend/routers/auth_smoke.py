"""JWT + CSRF smoke endpoints — no database, grafi_core only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from demo_backend.rate_limits import limiter
from demo_backend.settings import demo_cookie_names, demo_core_settings
from grafi_core.auth.user_jwt import issue_user_access_token, parse_user_access_token
from grafi_core.security.csrf import issue_csrf_token, set_csrf_cookie

router = APIRouter(prefix="/auth", tags=["demo-auth"])


class SmokeLoginRequest(BaseModel):
    user_id: int = Field(default=1, ge=1)


class SmokeLoginResponse(BaseModel):
    access_token: str
    user_id: int


class SmokeMeResponse(BaseModel):
    user_id: int


def _parse_demo_user(request: Request) -> int:
    cookies = demo_cookie_names()
    token = (request.cookies.get(cookies.user_token) or "").strip()
    if not token:
        auth = (request.headers.get("authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    settings = demo_core_settings()
    return parse_user_access_token(token, core_settings=settings)


@router.get("/csrf")
def demo_csrf(request: Request, response: Response):
    token = issue_csrf_token()
    set_csrf_cookie(
        response,
        token,
        secure=(request.url.scheme == "https"),
        cookie_names=demo_cookie_names(),
    )
    return {"csrf_token": token}


@router.post("/smoke-login", response_model=SmokeLoginResponse)
@limiter.limit("30/minute")
def demo_smoke_login(request: Request, response: Response, payload: SmokeLoginRequest):
    settings = demo_core_settings()
    token = issue_user_access_token(payload.user_id, core_settings=settings)
    cookies = demo_cookie_names()
    response.set_cookie(
        cookies.user_token,
        token,
        httponly=True,
        secure=(request.url.scheme == "https"),
        samesite="lax",
        path="/",
    )
    csrf_tok = issue_csrf_token()
    set_csrf_cookie(
        response,
        csrf_tok,
        secure=(request.url.scheme == "https"),
        cookie_names=cookies,
    )
    return SmokeLoginResponse(access_token=token, user_id=payload.user_id)


@router.get("/me", response_model=SmokeMeResponse)
def demo_me(user_id: int = Depends(_parse_demo_user)):
    return SmokeMeResponse(user_id=user_id)


@router.post("/smoke-action")
def demo_smoke_action(user_id: int = Depends(_parse_demo_user)):
    """Authenticated POST protected by CSRF (not on exempt list)."""
    return {"ok": True, "user_id": user_id}


@router.get("/jwt-smoke")
def demo_jwt_smoke():
    """Issue a token without cookies — utility for scripts and tests."""
    settings = demo_core_settings()
    user_id = 42
    token = issue_user_access_token(user_id, core_settings=settings)
    parsed = parse_user_access_token(token, core_settings=settings)
    return {"issued_for": user_id, "parsed_user_id": parsed, "token_prefix": token[:16]}
