"""SMTP credential proof helpers — safe previews, .env vs runtime comparison (no secrets logged)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from env_loader import BACKEND_DIR, backend_env_files_loaded, load_backend_env

SMTP_KEYS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_USE_TLS")


def mask_smtp_identity(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if "@" in raw:
        local, domain = raw.rsplit("@", 1)
        return f"{local[:1] or '*'}***@{domain.lower()}"
    return f"{raw[:2]}***" if len(raw) > 2 else "***"


def password_preview(password: str) -> dict[str, Any]:
    pw = password or ""
    n = len(pw)
    return {
        "password_length": n,
        "password_preview": "[REDACTED]" if n else "(empty)",
    }


def _read_env_file_values() -> dict[str, str]:
    env_file = BACKEND_DIR / ".env"
    if not env_file.is_file():
        return {}
    raw = dotenv_values(env_file)
    return {k: (v or "").strip() for k, v in raw.items() if k in SMTP_KEYS and v is not None}


def _runtime_smtp_values() -> dict[str, str]:
    load_backend_env()
    return {k: (os.environ.get(k) or "").strip() for k in SMTP_KEYS}


def _field_compare(key: str, file_val: str, runtime_val: str) -> dict[str, Any]:
    if key == "SMTP_PASSWORD":
        file_prev = password_preview(file_val)
        run_prev = password_preview(runtime_val)
        match = file_val == runtime_val
        return {
            "field": key,
            "match": match,
            "env_file": file_prev,
            "runtime": run_prev,
        }
    return {
        "field": key,
        "match": file_val == runtime_val,
        "env_file": file_val or None,
        "runtime": runtime_val or None,
    }


def smtp_credential_proof_report() -> dict[str, Any]:
    """
    Compare SMTP_* in backend/.env (dotenv_values) vs os.environ after load_backend_env().

    Note: load_dotenv(override=False) — keys already set in the process environment
    before .env load are NOT replaced by .env file values.
    """
    file_vals = _read_env_file_values()
    runtime_vals = _runtime_smtp_values()
    comparisons = [_field_compare(k, file_vals.get(k, ""), runtime_vals.get(k, "")) for k in SMTP_KEYS]

    return {
        "env_files_loaded": backend_env_files_loaded(),
        "dotenv_override": False,
        "env_file_path": str((BACKEND_DIR / ".env").resolve()) if (BACKEND_DIR / ".env").is_file() else None,
        "smtp_user_runtime_masked": mask_smtp_identity(runtime_vals.get("SMTP_USER", "")),
        "smtp_host_runtime": runtime_vals.get("SMTP_HOST") or None,
        "smtp_from_runtime": runtime_vals.get("SMTP_FROM") or None,
        "smtp_port_runtime": runtime_vals.get("SMTP_PORT") or None,
        "smtp_use_tls_runtime": runtime_vals.get("SMTP_USE_TLS") or None,
        "smtp_password_runtime": password_preview(runtime_vals.get("SMTP_PASSWORD", "")),
        "comparisons": comparisons,
        "all_match": all(c["match"] for c in comparisons if c["field"] in file_vals or c["runtime"]),
        "mismatched_fields": [c["field"] for c in comparisons if not c["match"]],
    }
