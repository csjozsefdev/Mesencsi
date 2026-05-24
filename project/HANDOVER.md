# Mesencsi — Handover & Review Guide (English)

Simple guide for developers, reviewers, or acceptance checks.  
**Stack:** FastAPI backend + static frontend (HTML/JS/CSS), PostgreSQL, Barion payments.

**Continuing work?** Read [PROJECT_CONTINUATION.md](PROJECT_CONTINUATION.md) first (current state, what is done, what is next).  
**Acceptance review?** Use [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md).

---

## 1. What this project is

| Part | Path | Role |
|------|------|------|
| Backend API | `backend/` | Shop, auth, orders, Barion, admin API |
| Storefront | `frontend/` | Customer site (`mesencsi.html`, `app.js`) |
| Admin UI | `frontend/admin.html` | Owner / maintenance panel |
| E2E tests | `e2e/` | Playwright (optional, needs Node.js) |
| DB migrations | `backend/alembic/` | PostgreSQL schema |

**One server in dev:** `run.bat` serves API + frontend on `http://127.0.0.1:8000`.

---

## 2. Quick start (reviewer)

```powershell
cd backend
copy .env.example .env
# Fill: POSTGRES_*, USER_JWT_SECRET, ADMIN_JWT_SECRET, OWNER_PASSWORD (bcrypt hash)

docker compose up -d          # optional: Postgres + Mailpit
.\run.bat
```

Open:

- Store: http://127.0.0.1:8000/
- Admin login: http://127.0.0.1:8000/admin/login
- API docs: http://127.0.0.1:8000/docs

---

## 3. Automated checks (must pass for code handover)

Run from `backend/`:

| Check | Command | Expected |
|-------|---------|----------|
| Backend tests | `.\scripts\gate_pytest.ps1` | `88+ passed`, few skipped OK |
| Health | `GET /health` | HTTP 200, `status: ok` |
| Barion config preview | `GET /payments/barion/status` | JSON with `sandbox`, `pos_key_configured` |
| Frontend assets | `GET /images/mesencsi-bg.jpg` | HTTP 200 (not 404) |

**Full gate (before release):**

```powershell
.\scripts\gate_full.ps1    # pytest + Playwright (backend must be running for E2E)
```

E2E needs Node.js: `cd e2e` → `npm install` → `npm test`.  
Details: [E2E_TESTING.md](E2E_TESTING.md).

---

## 4. Important environment variables

Copy from `backend/.env.example`. **Never commit `.env`.**

| Variable | Why it matters |
|----------|----------------|
| `USER_JWT_SECRET` | Shop login tokens |
| `ADMIN_JWT_SECRET` | Admin login tokens (separate from shop) |
| `POSTGRES_*` | Database |
| `OWNER_USERNAME` / `OWNER_PASSWORD` | Admin owner login (bcrypt hash) |
| `BARION_ENV` | `sandbox` for tests, `production` for live |
| `BARION_POS_KEY` | Real Barion API (empty = dev stub only) |
| `BARION_PAYEE_EMAIL` | Required for Payment/Start |
| `BARION_BACKEND_PUBLIC_URL` | Return + IPN URLs (HTTPS in production) |
| `BARION_IPN_SECRET` | IPN security (required in production) |
| `CORS_ALLOWED_ORIGINS` | Production only (no `*`) |
| `SMTP_*` | Verification + payment emails |
| `MESENCSI_PRODUCTION` | `true` enables strict production rules |

Production checklist: [backend/docs/deploy_readiness.md](backend/docs/deploy_readiness.md).

---

## 5. Core business rules (do not break)

These are implemented in code; reviewers should confirm behaviour in manual QA:

1. **Orders:** `POST /orders` only for **email-verified** users.
2. **Payment `paid`:** Only after Barion **GetPaymentState** sync (return URL or IPN), not from admin UI.
3. **Admin:** Order `completed` only when `payment_status = paid`.
4. **News comments:** Only **verified** users can post (403 otherwise).
5. **Barion IPN:** Returns HTTP 200; on sync failure includes `sync_failed: true` in JSON (for monitoring).

---

## 6. Key API endpoints (smoke)

| Area | Method | Path |
|------|--------|------|
| Health | GET | `/health` |
| Products | GET | `/products` |
| Register | POST | `/auth/register` |
| Login | POST | `/auth/login` |
| Orders | POST | `/orders` |
| Barion start | POST | `/payments/barion/start` |
| Barion return | GET | `/payments/barion/return` |
| Barion IPN | POST | `/payments/barion/ipn` |
| Admin login | POST | `/admin/login` |
| Admin orders | GET | `/admin/orders` |

---

## 7. Manual QA still required (not fully automated)

| Topic | Document |
|-------|----------|
| Barion sandbox payment | [BARION_SANDBOX_TESTING.md](BARION_SANDBOX_TESTING.md) |
| Full gate + E2E | [E2E_TESTING.md](E2E_TESTING.md) |
| Mobile UI quick check | [backend/docs/mobile_storefront_smoke_checklist.md](backend/docs/mobile_storefront_smoke_checklist.md) |
| Media uploads on deploy | [backend/docs/media_persistence_smoke.md](backend/docs/media_persistence_smoke.md) |
| Postgres smoke (optional) | [backend/docs/postgres_smoke.md](backend/docs/postgres_smoke.md) |

---

## 8. Handover status (honest summary)

| Level | Ready? |
|-------|--------|
| Source code + dev setup | **Yes** |
| Automated pytest gate | **Yes** |
| E2E infrastructure | **Yes** (must run locally with Node) |
| Manual QA sign-off | **Receiver must run** |
| Production go-live | **No** until infra + live Barion + SMTP + HTTPS |

---

## 9. Common reviewer failures

| Symptom | Likely cause |
|---------|----------------|
| Admin login fails | `ADMIN_JWT_SECRET` missing in `.env` |
| No background image | `frontend/images/mesencsi-bg.jpg` missing — run `python scripts/ensure_frontend_assets.py` or commit asset |
| Barion stub only | `BARION_POS_KEY` empty |
| IPN never updates order | Local dev without public HTTPS tunnel |
| pytest fails | Wrong Python / not using `.venv` |
| E2E fails | Backend not running or Node not installed |

---

## 10. Related docs index

| File | Purpose |
|------|---------|
| [PROJECT_CONTINUATION.md](PROJECT_CONTINUATION.md) | Where we left off — start here to continue work |
| [HANDOVER.md](HANDOVER.md) | This file |
| [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md) | Pass/fail acceptance checklist |
| [backend/README.md](backend/README.md) | Backend quick start |
| [backend/docs/gate_commands.md](backend/docs/gate_commands.md) | Gate scripts |
| [E2E_TESTING.md](E2E_TESTING.md) | Playwright + gate order |
| [BARION_SANDBOX_TESTING.md](BARION_SANDBOX_TESTING.md) | Payment testing |
| [backend/docs/deploy_readiness.md](backend/docs/deploy_readiness.md) | Production deploy |
