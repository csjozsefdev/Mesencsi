# Grafi Backend Core — Integration Contract

**Version:** 0.4.0 (Milestone 4B)  
**Package path:** `backend/grafi_core/`  
**Status:** Reusable starter template (`grafi_starter/`) + smoke demo (`demo_backend/`) consume core directly.

---

## Purpose

Grafi Backend Core provides reusable FastAPI infrastructure for Grafi client projects (KeepMeRollin, future webshops). Milestone 1 delivers **GREEN modules only** — security, JWT, SMTP config, logging, Barion HTTP client, metrics, and env loading — with configurable settings and no Mesencsi imports.

Consuming applications supply:

- Domain models and routers (orders, products, content)
- Branded email templates and frontend URL shapes
- Business health checks and startup validation extensions
- Database migrations for app-specific tables

---

## What is included (Milestone 1)

| Module | Path | Notes |
|--------|------|-------|
| Password crypto | `grafi_core.auth.password` | bcrypt hash/verify |
| Shop JWT | `grafi_core.auth.user_jwt` | Configurable env keys |
| Admin JWT | `grafi_core.auth.admin_jwt` | Separate secret + `typ=admin` |
| CSRF | `grafi_core.security.csrf` | Double-submit; configurable cookie names |
| Security headers | `grafi_core.security.headers` | CSP, HSTS when production |
| CORS | `grafi_core.security.cors` | Dev defaults; strict production |
| Rate limits | `grafi_core.security.rate_limits` | slowapi; optional Redis |
| App logging | `grafi_core.logging.app_logging` | `log_event`, `safe_log_extra` |
| SMTP config | `grafi_core.email.config` | Mode detection, hosted rules |
| Email errors | `grafi_core.email.errors` | `EmailNotConfiguredError`, `EmailSendError` |
| Barion client | `grafi_core.payments.barion_client` | REST v2 Start + GetPaymentState |
| Metrics | `grafi_core.ops.metrics` | In-memory counters + token endpoint |
| Env loader | `grafi_core.ops.env_loader` | `.env` load with pytest skip |
| Settings | `grafi_core.settings.*` | `CoreSettings`, `CookieNames`, JWT/SMTP settings |
| Protocols | `grafi_core.protocols.user_auth` | `UserAuthRepository` for Milestone 2 |

---

## What is included (Milestone 3 — YELLOW modules)

| Module | Path | Notes |
|--------|------|-------|
| Login throttle | `grafi_core.auth.login_throttle` | Settings, store protocol, assert/record/clear |
| Email verify tokens | `grafi_core.auth.email_verify` | Issue, expiry, resend cooldown (no ORM) |
| Password reset tokens | `grafi_core.auth.password_reset` | Hash, TTL validation (no ORM) |
| Startup helpers | `grafi_core.ops.startup_helpers` | `secret_ok`, `https_public_url`, `StartupConfigError` |
| Incident support | `grafi_core.ops.incident_support` | `RequestIdMiddleware`, injectable persist |
| SMTP transport | `grafi_core.email.transport` | `smtp_session`, `send_plain_email_via_smtp` |

Mesencsi adapters: `adapters/login_throttle_store.py`, `adapters/user_auth_repository.py` (`MesencsiUserAuthRepository`), `adapters/incidents.py`.

Auth HTTP routers split: `routers/user_auth.py`, `routers/admin_auth.py` (profile routes remain in `routers/user_mvp.py`).

---

## Reusable consumer templates (Milestone 4)

| Package | Path | Purpose |
|---------|------|---------|
| Smoke demo | `backend/demo_backend/` | Minimal proof: JWT/CSRF/health smoke only (M4A) |
| Starter app | `backend/grafi_starter/` | Copy-ready FastAPI template: DB, auth, CORS, incidents (M4B) |

Both import **`grafi_core` directly** — no Mesencsi shims. Use `grafi_starter` as the base when spinning up a new Grafi client backend.

```powershell
cd backend
$env:USER_JWT_SECRET = "your-local-secret-at-least-32-characters"
.\.venv\Scripts\uvicorn.exe grafi_starter.app:app --reload --port 8098
```

Run starter tests: `pytest grafi_starter/tests/ -v`

---

## What is NOT included (Milestone 3)

- Branded email templates and dev link logging (`email_outbound.py` templates stay Mesencsi-local; production SMTP uses core transport)
- Payment sync router orchestration (`payments_barion.py` body)
- Order/checkout domain

See [MESENCSI_BACKEND_CORE_EXTRACTION_AUDIT.md](../../MESENCSI_BACKEND_CORE_EXTRACTION_AUDIT.md) for full scope.

---

## Quick start (new project)

```python
from pathlib import Path

from grafi_core.settings.core_settings import CoreSettings
from grafi_core.settings.cookie_names import CookieNames
from grafi_core.security.csrf import CsrfConfig, CsrfMiddleware
from grafi_core.security.headers import register_security_headers
from grafi_core.security.cors import resolve_cors_allow_origins
from grafi_core.ops.env_loader import load_env_files

config_dir = Path(__file__).resolve().parent
load_env_files(config_dir)

settings = CoreSettings.from_env(config_dir=config_dir)
cookies = CookieNames()  # or CookieNames(user_token="myapp_token", ...)

# In FastAPI app factory:
# app.add_middleware(CsrfMiddleware, config=CsrfConfig(cookie_names=cookies))
# register_security_headers(app, core_settings=settings)
# origins = resolve_cors_allow_origins(settings)
```

Run core tests:

```powershell
cd backend
python -m pytest grafi_core/tests/ -v
```

---

## Mesencsi env mapping (Milestone 2 adapters)

When Mesencsi switches to core (planned Milestone 2), map existing env vars via thin adapters — **no env renames required initially**:

| Mesencsi env / constant | Grafi Core equivalent |
|-------------------------|----------------------|
| `MESENCSI_PRODUCTION` | `CoreSettings(production_env_key="MESENCSI_PRODUCTION").is_production()` |
| `mesencsi_user_token` | `CookieNames.mesencsi_defaults().user_token` |
| `mesencsi_admin_token` | `CookieNames.mesencsi_defaults().admin_token` |
| `mesencsi_csrf` | `CookieNames.mesencsi_defaults().csrf` |
| `USER_JWT_SECRET` | Default `ShopJwtSettings.secret_env_key` |
| `ADMIN_JWT_SECRET` | Default `AdminJwtSettings.secret_env_key` |
| `SMTP_*` | Default `SmtpSettings` env keys (unchanged) |
| `BARION_*` | Used directly by `barion_client` (unchanged) |
| Logger `mesencsi.*` | `CoreSettings(logger_prefix="mesencsi")` |

Example adapter (Milestone 2 — implemented):

```python
# backend/adapters/grafi_settings.py
from grafi_core.settings.core_settings import CoreSettings
from grafi_core.settings.cookie_names import CookieNames

def mesencsi_core_settings() -> CoreSettings:
    return CoreSettings(
        app_name="mesencsi",
        logger_prefix="mesencsi",
        production_env_key="MESENCSI_PRODUCTION",
        test_database_url_env_key="MESENCSI_TEST_DATABASE_URL",
    )

def mesencsi_cookie_names() -> CookieNames:
    return CookieNames.mesencsi_defaults()
```

Mesencsi modules (`password_utils.py`, `user_tokens.py`, `csrf.py`, etc.) are thin shims that delegate to `grafi_core` using these adapters. Import paths across the app are unchanged.

---

## UserAuthRepository (Milestone 2 target)

Core defines a minimal protocol; Mesencsi `AppUser` will implement it via an adapter:

```python
from grafi_core.protocols.user_auth import UserAuthRecord, UserAuthRepository

# App implements find_by_email / find_by_id returning objects with:
# id, email, password_hash, email_verified_at, is_banned, is_deleted
```

The fat `AppUser` profile fields (shipping, avatar, etc.) stay in Mesencsi — not in core.

---

## Migration stages

| Stage | Scope |
|-------|--------|
| **M1 (done)** | Copy GREEN modules to `grafi_core/`; core tests; no Mesencsi wiring |
| **M2 (done)** | `adapters/grafi_settings.py`; 13 thin shims delegate to `grafi_core`; zero pytest regression |
| **M3 (done)** | YELLOW modules, adapters, auth router splits, core tests for M3 |
| **M4A (done)** | Minimal smoke demo (`demo_backend/`) — proves direct `grafi_core` import |
| **M4B (done)** | Reusable starter template (`grafi_starter/`) — DB, `UserAuthRepository`, generic auth |
| **M5** | Optional: publish `grafi_core` as pip package; extract starter to separate repo |

---

## Testing strategy

- **Core tests:** `backend/grafi_core/tests/` — run independently
- **Mesencsi tests:** `backend/tests/` — must remain green; unchanged in M1
- **Gate:** Both suites pass before merging Milestone 1

New tests added in M1 (audit gaps):

- Shop JWT expiry, wrong `typ`, malformed `sub`, missing secret
- Admin JWT expiry, shop token rejection, invalid role
- `safe_log_extra` redaction
- Barion status mapping including `PartiallySucceeded`
- Email config modes (relay, mailpit, Brevo, Resend)
- Env loader pytest skip

---

## Parallel track: Barion sandbox validation

Barion client code is in core; full payment flow remains in Mesencsi until Milestone 3. Real sandbox E2E validation is documented in [BARION_SANDBOX_TESTING.md](../../BARION_SANDBOX_TESTING.md) and does not block Milestone 1.

**Barion status:** Implemented / code-tested / pending real sandbox merchant validation.

---

## Non-goals for Milestone 3

- Renaming Mesencsi env vars to `GRAFI_*`
- Extracting Mesencsi-branded email HTML templates to core
- Moving or deleting original backend module files (they are shims)
- Publishing core as a separate pip package (optional future step)

---

*Milestone 3 completed in sandbox copy. Original Mesencsi project untouched.*
