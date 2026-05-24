#!/usr/bin/env python3
"""
Set admin login username/password (bcrypt in .env) and ensure ADMIN_JWT_SECRET exists.

Run from backend folder:
  python scripts/setup_admin_credentials.py --owner-username YOUR_NAME --owner-password "YourPassword"
  python scripts/setup_admin_credentials.py --owner-username YOUR_NAME --owner-password "YourPassword" --maintenance-username maint2 --maintenance-password "MaintPass123!"
  python scripts/setup_admin_credentials.py --maintenance-only --maintenance-username maint2 --maintenance-password "MaintPass123!"

Restarts uvicorn after changes so new env loads.
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from password_utils import hash_password  # noqa: E402

_ENV_PATH = _BACKEND / ".env"


def _upsert_env_line(lines: list[str], key: str, value: str) -> list[str]:
    pattern = re.compile(rf"^{re.escape(key)}=", re.IGNORECASE)
    out: list[str] = []
    found = False
    for line in lines:
        if pattern.match(line.strip()):
            out.append(f"{key}={value}\n")
            found = True
        else:
            out.append(line if line.endswith("\n") else line + "\n")
    if not found:
        if out and not out[-1].endswith("\n"):
            out[-1] = out[-1] + "\n"
        out.append(f"{key}={value}\n")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Update admin credentials in backend/.env")
    p.add_argument("--jwt-only", action="store_true", help="Only set ADMIN_JWT_SECRET if missing (no password change)")
    p.add_argument(
        "--maintenance-only",
        action="store_true",
        help="Only update MAINTENANCE_USERNAME / MAINTENANCE_PASSWORD (owner left unchanged)",
    )
    p.add_argument("--owner-username", default="", help="OWNER_USERNAME (admin login name)")
    p.add_argument("--owner-password", default="", help="Plain password (hashed into OWNER_PASSWORD)")
    p.add_argument("--maintenance-username", default="", help="MAINTENANCE_USERNAME (optional)")
    p.add_argument("--maintenance-password", default="", help="MAINTENANCE_PASSWORD plain (optional)")
    p.add_argument(
        "--admin-jwt-secret",
        default="",
        help="ADMIN_JWT_SECRET (optional; auto-generates 48 chars if missing in .env)",
    )
    args = p.parse_args()

    if args.jwt_only and args.maintenance_only:
        print("ERROR: use either --jwt-only or --maintenance-only, not both.", file=sys.stderr)
        return 2

    if not _ENV_PATH.is_file():
        print(f"ERROR: {_ENV_PATH} not found. Copy .env.example to .env first.", file=sys.stderr)
        return 2

    text = _ENV_PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines:
        lines = ["\n"]

    if args.maintenance_only:
        maint_user = args.maintenance_username.strip()
        if not maint_user:
            print("ERROR: --maintenance-username required with --maintenance-only.", file=sys.stderr)
            return 2
        if len(args.maintenance_password) < 8:
            print("ERROR: maintenance password should be at least 8 characters.", file=sys.stderr)
            return 2
        lines = _upsert_env_line(lines, "MAINTENANCE_USERNAME", maint_user)
        lines = _upsert_env_line(lines, "MAINTENANCE_PASSWORD", hash_password(args.maintenance_password))
    elif not args.jwt_only:
        owner_user = args.owner_username.strip()
        if not owner_user:
            print(
                "ERROR: --owner-username and --owner-password required.\n"
                "  Or: --maintenance-only with maintenance username/password\n"
                "  Or: --jwt-only to only add ADMIN_JWT_SECRET",
                file=sys.stderr,
            )
            return 2
        if len(args.owner_password) < 8:
            print("ERROR: owner password should be at least 8 characters.", file=sys.stderr)
            return 2
        lines = _upsert_env_line(lines, "OWNER_USERNAME", owner_user)
        lines = _upsert_env_line(lines, "OWNER_PASSWORD", hash_password(args.owner_password))
        if args.maintenance_username.strip():
            if not args.maintenance_password:
                print("ERROR: --maintenance-password required when maintenance username is set.", file=sys.stderr)
                return 2
            lines = _upsert_env_line(lines, "MAINTENANCE_USERNAME", args.maintenance_username.strip())
            lines = _upsert_env_line(lines, "MAINTENANCE_PASSWORD", hash_password(args.maintenance_password))

    # ADMIN JWT — required for POST /admin/login
    existing_admin_jwt = ""
    for line in lines:
        if line.strip().startswith("ADMIN_JWT_SECRET="):
            existing_admin_jwt = line.split("=", 1)[1].strip()
            break
    admin_secret = (args.admin_jwt_secret or existing_admin_jwt or "").strip()
    if not admin_secret or "replace_with" in admin_secret.lower():
        admin_secret = secrets.token_urlsafe(48)
    lines = _upsert_env_line(lines, "ADMIN_JWT_SECRET", admin_secret)

    _ENV_PATH.write_text("".join(lines), encoding="utf-8")

    print("OK: updated", _ENV_PATH)
    if args.maintenance_only:
        print(f"  MAINTENANCE_USERNAME={args.maintenance_username.strip()}")
        print("  MAINTENANCE_PASSWORD=<bcrypt hash written>")
    elif not args.jwt_only:
        print(f"  OWNER_USERNAME={args.owner_username.strip()}")
        print("  OWNER_PASSWORD=<bcrypt hash written>")
        if args.maintenance_username.strip():
            print(f"  MAINTENANCE_USERNAME={args.maintenance_username.strip()}")
            print("  MAINTENANCE_PASSWORD=<bcrypt hash written>")
    if not args.maintenance_only:
        print("  ADMIN_JWT_SECRET=<checked — restart uvicorn to load>")
    print()
    print("Next: stop run.bat (Ctrl+C) and start .\\run.bat again, then login at /admin/login")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
