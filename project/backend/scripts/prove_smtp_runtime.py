#!/usr/bin/env python3
"""
Prove SMTP runtime credentials vs backend/.env and attempt SMTP login.

Run from backend/:
  .\\.venv\\Scripts\\python.exe scripts\\prove_smtp_runtime.py

Prints JSON-safe report to stdout (no full secrets).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from email_outbound import _smtp_session, _smtp_settings
from smtp_credential_proof import password_preview, smtp_credential_proof_report


def main() -> int:
    report = smtp_credential_proof_report()
    host, port, user, password, mail_from, use_tls = _smtp_settings()

    login_result: dict[str, object] = {"attempted": bool(user)}
    if user:
        try:
            with _smtp_session(
                host=host,
                port=port,
                user=user,
                password=password,
                use_tls=use_tls,
            ):
                pass
            login_result["success"] = True
        except Exception as e:
            login_result["success"] = False
            login_result["exception_type"] = type(e).__name__
            login_result["exception_message"] = str(e)

    out = {
        "credential_proof": report,
        "login_probe": login_result,
        "runtime_at_login": {
            "host": host,
            "port": port,
            "smtp_user_exact": user,
            "smtp_from": mail_from,
            "password": password_preview(password),
        },
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))

    if report.get("mismatched_fields"):
        print("\nCONCLUSION: A — Runtime credentials differ from .env file", file=sys.stderr)
        return 10
    if login_result.get("success") is False:
        print("\nCONCLUSION: B — Runtime matches .env; SMTP login failed", file=sys.stderr)
        return 11
    print("\nCONCLUSION: login succeeded", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
