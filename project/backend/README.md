# Mesencsi — backend (FastAPI)

Webshop API: products, cart, guest checkout, Barion payments, admin CMS, email outbox.

**Full documentation:** [docs/README.md](docs/README.md)

---

## Quick start (Windows)

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Postgres via compose).
2. Copy `.env.example` → `.env`, set `POSTGRES_PASSWORD` and JWT secrets.
3. Start Postgres: `docker compose up -d`
4. Run: `.\run.bat`

Opens on http://127.0.0.1:8000/ (store) and http://127.0.0.1:8000/admin/login (admin).

`run.bat` creates `.venv`, installs deps, runs Alembic migrations, and starts Uvicorn with the project Python.

---

## Documentation

| Topic | Link |
|-------|------|
| **Index** | [docs/README.md](docs/README.md) |
| Local development | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| API reference | [docs/API.md](docs/API.md) |
| Environment variables | [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) |
| Production deploy | [docs/deploy_readiness.md](docs/deploy_readiness.md) |
| Operations | [docs/ops_runbook.md](docs/ops_runbook.md) |
| Handover (English) | [../HANDOVER.md](../HANDOVER.md) |
| Review checklist | [../REVIEW_CHECKLIST.md](../REVIEW_CHECKLIST.md) |

---

## Gate commands

```powershell
.\scripts\gate_pytest.ps1       # 347 backend tests
.\scripts\gate_full.ps1         # pytest + Playwright E2E
python scripts\predeploy_alembic_check.py
```

---

## Production

```powershell
pip install -r requirements-prod.txt
python scripts\predeploy_alembic_check.py
.venv\Scripts\python.exe -m alembic upgrade head
# uvicorn / gunicorn with MESENCSI_PRODUCTION=true
# cron: python scripts\process_email_outbox.py
```

Alembic head: **`032_storybook_page_image_layout`**
