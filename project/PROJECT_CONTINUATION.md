# Mesencsi — Where we left off (continuation guide)

**Read this first** if you continue development or QA on an existing machine.  
**Last updated:** June 2026 (production hardening complete — code + tests).

For a clean reviewer overview, see [HANDOVER.md](HANDOVER.md).  
For tick-box acceptance, see [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md).  
For production deploy, see [backend/docs/deploy_readiness.md](backend/docs/deploy_readiness.md).

---

## 1. Project state in one sentence

**Backend is production-hardened and pytest-green (~300 tests);** manual sandbox Barion QA, E2E, legal pages, and live infra (HTTPS, SMTP cron, media persistence) are still on the **deploy owner**.

---

## 2. What is already done

### Code & tests

- FastAPI backend: auth, orders, Barion (REST + IPN + return sync), admin API, news, gallery, storybooks.
- Static frontend: storefront (`mesencsi.html` + `app.js`), admin (`admin.html`).
- **~300 pytest tests** passing (SQLite in-memory); optional Postgres alembic smoke.
- Alembic head: **`029`** (email/token_version, outbox, idempotency, integrity constraints).

### Production hardening (June 2026)

| Area | What |
|------|------|
| Barion | Full checkout group required on `start` (409 if partial) |
| Auth | Email lowercase + case-insensitive login; JWT `token_version` |
| Admin | Owner-only: verify/ban/delete users, delete order line, `payment_status` |
| Startup | `MESENCSI_PRODUCTION=true` validates secrets, bcrypt, HTTPS, SMTP |
| Email | Payment confirmation → `email_outbox` + `process_email_outbox.py` cron |
| Orders | `Idempotency-Key` header on `POST /orders` |
| DB | CHECK constraints; unique `lower(email)` |
| Deploy | `requirements-prod.txt`, `predeploy_alembic_check.py`, migration 007 docs |

### Tooling & docs

| Item | Location |
|------|----------|
| Handover guide | [HANDOVER.md](HANDOVER.md) |
| Review checklist | [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md) |
| Production deploy | [backend/docs/deploy_readiness.md](backend/docs/deploy_readiness.md) |
| Ops runbook | [backend/docs/ops_runbook.md](backend/docs/ops_runbook.md) |
| Gate scripts | `backend/scripts/gate_pytest.ps1`, `gate_e2e.ps1`, `gate_full.ps1` |
| E2E (Playwright) | `e2e/` + [E2E_TESTING.md](E2E_TESTING.md) |
| Barion sandbox QA | [BARION_SANDBOX_TESTING.md](BARION_SANDBOX_TESTING.md) |

---

## 3. What is NOT done (your job next)

### Must-do before production go-live

1. **Owner manual QA** — [pre_production_qa.md](backend/docs/pre_production_qa.md).
2. **Barion sandbox E2E** with real `BARION_POS_KEY` — [BARION_SANDBOX_TESTING.md](BARION_SANDBOX_TESTING.md).
3. **SMTP + email outbox cron** — verify + payment confirmation via `process_email_outbox.py`.
4. **Legal pages** — [production_legal_todo.md](backend/docs/production_legal_todo.md) (client/counsel).
5. **E2E** — `cd e2e && npm test` (backend running).
6. **Media persistence** — persistent disk or S3 on target host.

### Production infra (separate from code)

- Live Barion merchant + `BARION_ENV=production`.
- HTTPS URLs for return/IPN.
- `MESENCSI_PRODUCTION=true` + full env.
- `REDIS_URL` if multiple workers.
- CI pipeline wiring (commands exist in docs).

---

## 4. Start here (15 minutes)

```powershell
# Terminal 1 — backend
cd backend
.\run.bat

# Terminal 2 — checks
cd backend
.\scripts\gate_pytest.ps1
python scripts/predeploy_alembic_check.py
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/payments/barion/status
```

Open:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/admin/login

Check `.env` has at least: `USER_JWT_SECRET`, `ADMIN_JWT_SECRET`, `POSTGRES_*`, `BARION_ENV=sandbox`, `BARION_POS_KEY` + `BARION_PAYEE_EMAIL`.

---

## 5. Recommended work order

| Order | Task | Done when |
|-------|------|-----------|
| 1 | `gate_pytest.ps1` green | ~300 tests pass |
| 2 | `predeploy_alembic_check.py` + `alembic upgrade head` | head `029` |
| 3 | Manual storefront + admin smoke | [REVIEW_CHECKLIST](REVIEW_CHECKLIST.md) A–G |
| 4 | Barion sandbox full flow | [BARION_SANDBOX_TESTING](BARION_SANDBOX_TESTING.md) |
| 5 | SMTP + outbox script | Confirmation email delivered |
| 6 | `npm test` in `e2e/` | Playwright green |
| 7 | `gate_full.ps1` | pytest + E2E |
| 8 | Production deploy | [deploy_readiness](backend/docs/deploy_readiness.md) |

---

## 6. Architecture reminder (where to edit)

| Change | Look in |
|--------|---------|
| Shop API routes | `backend/mesencsi.py`, `backend/routers/` |
| Barion | `backend/routers/payments_barion.py`, `backend/barion_api.py` |
| Admin API | `backend/admin_routes.py` |
| Email outbox | `backend/email_outbox_worker.py`, `payment_confirmation_email.py` |
| Startup validation | `backend/startup_config.py` |
| Storefront UI | `frontend/app.js`, `frontend/mesencsi.html` |
| Admin UI | `frontend/admin.html` |
| DB models | `backend/db_models.py` + Alembic `backend/alembic/versions/` |
| Tests | `backend/tests/` |

**Do not change without product sign-off:** `paid` rules, Barion verify-only path, owner-only admin restrictions.

---

## 7. Doc map

| I need to… | Open |
|------------|------|
| Continue coding | **This file** |
| Onboard a reviewer | [HANDOVER.md](HANDOVER.md) |
| Grade / accept delivery | [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md) |
| Test Barion | [BARION_SANDBOX_TESTING.md](BARION_SANDBOX_TESTING.md) |
| Run E2E / gates | [E2E_TESTING.md](E2E_TESTING.md) |
| Deploy live | [backend/docs/deploy_readiness.md](backend/docs/deploy_readiness.md) |
| Operate production | [backend/docs/ops_runbook.md](backend/docs/ops_runbook.md) |
| Start backend only | [backend/README.md](backend/README.md) |

---

## 8. Handoff line

> Code and ~300 automated backend tests are production-hardened. Run manual Barion + SMTP/outbox QA, legal sign-off, then deploy with HTTPS, live Barion, outbox cron, and upload storage — see deploy_readiness and ops_runbook.
