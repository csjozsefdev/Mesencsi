"""Admin authentication: login, logout, session probe."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from auth import authenticate_admin, create_admin_token
from auth_limits import limiter
from csrf import issue_csrf_token, set_csrf_cookie
from dependencies import CurrentAdmin, require_role

router = APIRouter(tags=["admin-auth"])


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    token: str
    username: str
    role: str


@router.post("/login", response_model=AdminLoginResponse)
@limiter.limit("12/minute")
def admin_login(request: Request, payload: AdminLoginRequest, response: Response):
    username, role = authenticate_admin(payload.username, payload.password)
    token = create_admin_token(username=username, role=role)
    response.set_cookie(
        "mesencsi_admin_token",
        token,
        httponly=True,
        secure=(request.url.scheme == "https"),
        samesite="lax",
        path="/",
    )
    csrf_tok = issue_csrf_token()
    set_csrf_cookie(response, csrf_tok, secure=(request.url.scheme == "https"))
    return {"token": token, "username": username, "role": role}


@router.post("/logout")
def admin_logout(response: Response):
    response.delete_cookie("mesencsi_admin_token", path="/")
    return {"ok": True}


@router.get("/me")
def admin_me(admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"]))):
    return {"username": admin.username, "role": admin.role}
