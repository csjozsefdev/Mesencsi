# Development guide

Local setup for the Mesencsi backend on Windows (recommended) or Linux/macOS.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Backend runtime |
| Docker Desktop | latest | Postgres + Mailpit (optional but recommended) |
| Git | — | Clone repo |

Node.js is only needed for Playwright E2E tests (`../../e2e/`).

---

## First-time setup

```powershell
cd backend
copy .env.example .env
```

Edit `.env`:

1. Set `POSTGRES_PASSWORD` (match `docker-compose.yml` or your own)
2. Set `USER_JWT_SECRET` and `ADMIN_JWT_SECRET` (min 32 chars)
3. Optionally set admin passwords: `python scripts/setup_admin_credentials.py`

Start infrastructure:

```powershell
docker compose up -d
```

This starts:

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL 16 | 5432 | Database (`mesencsi` / `mesencsi`) |
| Mailpit | 8025 (UI), 1025 (SMTP) | Dev email capture |

Start the server:

```powershell
.\run.bat
```

`run.bat` will:

1. Create `.venv` if missing
2. `pip install -r requirements.txt`
3. Check port 8000 is free
4. `alembic upgrade head`
5. `scripts/ensure_frontend_assets.py`
6. `uvicorn mesencsi:app --reload --host 127.0.0.1 --port 8000`

**URLs:**

- Store: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/login
- API docs: http://127.0.0.1:8000/docs
- Mailpit: http://127.0.0.1:8025/

Default admin credentials are in `.env.example` (change for anything beyond local dev).

---

## Linux / macOS

```bash
cd backend
cp .env.example .env
docker compose up -d
./run.sh
```

`run.sh` does not check port 8000 or run `ensure_frontend_assets.py`. Run manually if needed:

```bash
python scripts/ensure_frontend_assets.py
```

---

## Manual commands

Use the **same** `.venv\Scripts\python.exe` for every command:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn mesencsi:app --host 127.0.0.1 --port 8000 --reload
```

Or use the wrapper:

```powershell
.\uvicorn.bat mesencsi:app --reload --host 127.0.0.1 --port 8000
```

---

## Port 8000 already in use

`run.bat` checks if port 8000 is taken by a non-project process and refuses to start.

Typical cause: globally installed `uvicorn` running on another Python. Stop that process or change the port in `run.bat`.

---

## Email in development

| Mode | Setup | Behaviour |
|------|-------|-----------|
| No SMTP | Comment out `SMTP_HOST` | Verify/reset links in uvicorn log |
| Mailpit | `SMTP_HOST=127.0.0.1`, port `1025` | Emails in http://127.0.0.1:8025 |
| Gmail / Resend | Full SMTP vars | Real delivery |

Set `MESENCSI_DEV_LOG_AUTH_EMAIL_LINKS=true` to also log auth links when SMTP works.

See [local_auth_email_qa.md](./local_auth_email_qa.md).

---

## CORS / frontend on another port

Dev CORS defaults are in `cors_config.py` (Vite `5173`, Live Server `5500`).

For production: set `CORS_ALLOWED_ORIGINS` in `.env`.

---

## Testing

### Backend (primary gate)

```powershell
.\scripts\gate_pytest.ps1
# or
.venv\Scripts\python.exe -m pytest -q
```

347 tests, SQLite in-memory. Skips OK (e.g. Postgres smoke without URL).

### Pre-deploy DB check

```powershell
python scripts/predeploy_alembic_check.py
python -m alembic upgrade head
```

### Optional Postgres smoke

```powershell
$env:MESENCSI_POSTGRES_SMOKE_URL = "postgresql+psycopg://mesencsi:PASSWORD@localhost:5432/mesencsi_test"
python scripts/postgres_smoke.py
```

See [postgres_smoke.md](./postgres_smoke.md).

### E2E (Playwright)

Backend must be running. From project root:

```powershell
cd e2e
npm install
npm test
```

Or: `.\scripts\gate_full.ps1` (pytest + E2E).

See [../../E2E_TESTING.md](../../E2E_TESTING.md).

---

## Useful scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup_admin_credentials.py` | Set owner/maintenance bcrypt hashes |
| `scripts/apply_resend_smtp_env.py` | Write Resend SMTP block to `.env` |
| `scripts/process_email_outbox.py` | Process payment confirmation queue |
| `scripts/dev_seed_qa_shop_user.py` | Create verified test shop user |
| `scripts/dev_delete_shop_user_by_email.py` | Delete shop user by email (local only) |
| `scripts/dev_manual_verify_shop_user.py` | Manually verify email + clear throttle |
| `scripts/prove_smtp_runtime.py` | SMTP credential proof (JSON report) |
| `scripts/media_persistence_check.py` | Verify uploads directory writable |
| `scripts/ensure_frontend_assets.py` | Check/generate favicons and background |

Full list: [gate_commands.md](./gate_commands.md).

---

## Database migrations

```powershell
# Apply all migrations
.venv\Scripts\python.exe -m alembic upgrade head

# Create new migration (after model change)
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "description"

# Current head
.venv\Scripts\python.exe -m alembic current
```

**Warning:** Migration `007` deletes all existing orders. See [migration_007_warning.md](./migration_007_warning.md).

---

## Project layout

```
backend/
├── mesencsi.py          # App entry point
├── admin_routes.py      # Admin router aggregator
├── db_models.py         # SQLAlchemy models
├── routers/             # API route modules
├── alembic/             # Database migrations
├── tests/               # Pytest suite
├── scripts/             # Dev and ops scripts
├── docs/                # Documentation (you are here)
├── media/uploads/       # Local uploaded files
├── grafi_core/          # Shared library
└── demo_backend/        # grafi_core smoke app

frontend/                # Static storefront + admin (sibling folder)
e2e/                     # Playwright tests (project root)
```

---

## Common issues

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: sqlalchemy` | Use `.venv\Scripts\python.exe`, not global Python |
| Admin login fails | Set `ADMIN_JWT_SECRET` in `.env` |
| No background image | Run `python scripts/ensure_frontend_assets.py` |
| Barion stub only | `BARION_POS_KEY` is empty (expected in dev) |
| IPN never updates order | Local dev has no public HTTPS — use return URL or manual sync |
| pytest import errors | Activate venv or use full python path |

---

## Next steps

- [ARCHITECTURE.md](./ARCHITECTURE.md) — how the app is structured
- [API.md](./API.md) — endpoint reference
- [ENVIRONMENT.md](./ENVIRONMENT.md) — all env vars
- [../../HANDOVER.md](../../HANDOVER.md) — reviewer handover guide
