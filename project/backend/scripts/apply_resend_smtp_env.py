#!/usr/bin/env python3
"""
Update backend/.env SMTP_* block for Resend relay.

Usage (from backend/):
  set RESEND_API_KEY=re_...
  set RESEND_FROM=onboarding@resend.dev
  python scripts/apply_resend_smtp_env.py

Never commits secrets; reads API key only from env.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"

SMTP_KEYS = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USE_TLS",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
)

RESEND_VALUES: dict[str, str] = {
    "SMTP_HOST": "smtp.resend.com",
    "SMTP_PORT": "587",
    "SMTP_USE_TLS": "1",
    "SMTP_USER": "resend",
}


def _read_env_lines() -> list[str]:
    if not ENV_PATH.is_file():
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def _upsert(lines: list[str], key: str, value: str) -> list[str]:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    out: list[str] = []
    replaced = False
    for line in lines:
        if pattern.match(line):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    return out


def main() -> int:
    api_key = (os.environ.get("RESEND_API_KEY") or os.environ.get("SMTP_PASSWORD") or "").strip()
    mail_from = (os.environ.get("RESEND_FROM") or os.environ.get("SMTP_FROM") or "").strip()
    if not api_key.startswith("re_"):
        print(
            "Set RESEND_API_KEY=re_... (Resend API key) in the environment, then run again.",
            file=sys.stderr,
        )
        return 1
    if not mail_from or "@" not in mail_from:
        print(
            "Set RESEND_FROM=verified@sender.com (e.g. onboarding@resend.dev for sandbox).",
            file=sys.stderr,
        )
        return 2

    lines = _read_env_lines()
    for key, val in RESEND_VALUES.items():
        lines = _upsert(lines, key, val)
    lines = _upsert(lines, "SMTP_PASSWORD", api_key)
    lines = _upsert(lines, "SMTP_FROM", mail_from)

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Updated {ENV_PATH} for Resend SMTP (host={RESEND_VALUES['SMTP_HOST']}, from={mail_from}).")
    print("Restart uvicorn. Test: forgot-password or GET /dev/smtp-config")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
