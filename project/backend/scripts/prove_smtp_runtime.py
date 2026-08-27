#!/usr/bin/env python3
"""
Prove SMTP runtime credentials vs backend/.env, attempt SMTP login, and optionally
send exactly one real test email to an explicitly-provided recipient.

Run from backend/:
  .\\.venv\\Scripts\\python.exe scripts\\prove_smtp_runtime.py
  .\\.venv\\Scripts\\python.exe scripts\\prove_smtp_runtime.py --send-test-to you@example.com

Prints JSON-safe report to stdout (no full secrets).

--send-test-to is opt-in and off by default: with no flag, this script only connects and
authenticates (login probe), it never sends a message. When given, it sends exactly ONE
plain-text test email to the single address supplied on the command line — never to a
list, never to an address read from config — so a real send only happens when a human
explicitly names the recipient on that invocation.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from email.message import EmailMessage
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from email_outbound import _smtp_session, _smtp_settings
from smtp_credential_proof import mask_smtp_identity, password_preview, smtp_credential_proof_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--send-test-to",
        metavar="EMAIL",
        default=None,
        help="Opt-in: send exactly one real plain-text test email to this single address after a successful login probe.",
    )
    return parser.parse_args()


def _send_test_email(*, host: str, port: int, user: str, password: str, use_tls: bool, mail_from: str, to_email: str) -> dict[str, object]:
    message = EmailMessage()
    message["Subject"] = "Mesencsi SMTP runtime proof — test email"
    message["From"] = mail_from
    message["To"] = to_email
    sent_at = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    message.set_content(
        "This is a one-off SMTP runtime proof test email sent by scripts/prove_smtp_runtime.py.\n"
        f"Sent at: {sent_at}\n"
        "No action needed — this does not come from a real registration or password reset.\n"
    )
    result: dict[str, object] = {"attempted": True, "to": mask_smtp_identity(to_email)}
    try:
        with _smtp_session(host=host, port=port, user=user, password=password, use_tls=use_tls) as smtp:
            smtp.send_message(message)
        result["success"] = True
    except Exception as e:
        result["success"] = False
        result["exception_type"] = type(e).__name__
        result["exception_message"] = str(e)
    return result


def main() -> int:
    args = _parse_args()
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

    send_result: dict[str, object] | None = None
    if args.send_test_to and login_result.get("success"):
        send_result = _send_test_email(
            host=host,
            port=port,
            user=user,
            password=password,
            use_tls=use_tls,
            mail_from=mail_from,
            to_email=args.send_test_to,
        )
    elif args.send_test_to:
        send_result = {"attempted": False, "reason": "login_probe_did_not_succeed"}

    out = {
        "credential_proof": report,
        "login_probe": login_result,
        "test_send": send_result,
        "runtime_at_login": {
            "host": host,
            "port": port,
            "smtp_user_masked": mask_smtp_identity(user),
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
    if send_result is not None and send_result.get("success") is False:
        print("\nCONCLUSION: C — Login succeeded; test send failed", file=sys.stderr)
        return 12
    print("\nCONCLUSION: login succeeded" + (" and test email sent" if send_result and send_result.get("success") else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
