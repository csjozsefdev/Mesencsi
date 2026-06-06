# Mesencsi — Where we left off (continuation guide)

**Read this first** if you continue development or QA on an existing machine.  
**Last updated:** May 2026 (post handover / gate / E2E / pre-production audit).

For a clean reviewer overview, see [HANDOVER.md](HANDOVER.md).  
For tick-box acceptance, see [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md).  
For **Graph-ID** snapshot (now / next / nodes & edges), see [GRAPH_ID_STATUS.md](GRAPH_ID_STATUS.md).

---

## 1. Project state in one sentence

The **shop + admin + Barion payment code is in place and pytest-green**; **manual sandbox payment QA**, **first E2E run with Node**, and **production deploy** are still on the **next owner**.

---

## 2. What is already done

### Code & tests

- FastAPI backend: auth, orders, Barion (REST + IPN + return sync), admin API, news, gallery, storybooks.
- Static frontend: storefront (`mesencsi.html` + `app.js`), admin (`admin.html`).
- **~88 pytest tests** passing (SQLite in-memory in CI/local pytest).
- Guards: email verify for orders/comments; `paid` only via Barion GetPaymentState; admin `completed` only when paid.
- IPN returns `sync_failed: true` on sync errors (HTTP 200 kept for Barion retries).

### Tooling & docs (English)

| Item | Location |
|------|----------|
| Handover guide | [HANDOVER.md](HANDOVER.md) |
| Review checklist | [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md) |
| Gate scripts | `backend/scripts/gate_pytest.ps1`, `gate_e2e.ps1`, `gate_full.ps1` |
| E2E (Playwright) | `e2e/` + [E2E_TESTING.md](E2E_TESTING.md) |
| Barion sandbox QA plan | [BARION_SANDBOX_TESTING.md](BARION_SANDBOX_TESTING.md) |
| Production deploy | [backend/docs/deploy_readiness.md](backend/docs/deploy_readiness.md) |
| Gate order (4 steps) | Documented in [E2E_TESTING.md](E2E_TESTING.md) |

### Recent fixes (do not redo unless regressing)

- News comment POST: requires verified email (403 otherwise).
- Page background: uses `frontend/images/mesencsi-bg.jpg` (real artwork); **do not** regenerate over it with `gen_mesencsi_favicons.py` (favicons only now).
- Admin orphan routes: `#stories` → storybooks; dead `settings` nav removed from hash map.
- `ensure_frontend_assets.py` + startup check: warns if background missing; does not overwrite JPG.

### Minimal E2E hooks

`data-testid` on storefront/admin login for Playwright (see `e2e/helpers/selectors.ts`).

---

## 3. What is NOT done (your job next)

### Must-do before calling it “release ready”

1. **Run manual QA** — [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md) sections C–G.  
2. **Barion sandbox end-to-end** with real `BARION_POS_KEY` — [BARION_SANDBOX_TESTING.md](BARION_SANDBOX_TESTING.md).  
   - Use HTTPS tunnel (ngrok, etc.) if IPN from Barion must hit your machine.  
3. **SMTP** — verify email + payment confirmation (Mailpit locally or real SMTP).  
4. **First E2E run** — install Node.js, then `cd e2e && npm install && npm test` (backend running).  
5. **`gate_full.ps1`** once E2E works.

### Production (separate project)

- Live Barion merchant + `BARION_ENV=production`.
- HTTPS URLs for return/IPN.
- `MESENCSI_PRODUCTION=true` + full env ([deploy_readiness](backend/docs/deploy_readiness.md)).
- Persistent `media/uploads` (volume or object storage).
- CI pipeline (commands exist; not wired in repo).

### Nice-to-have / known gaps

- Root-level single README is thin; main entry is `backend/README.md` + this file.
- E2E not run in all dev environments (npm was missing on one machine).
- `ADMIN_JWT_SECRET` was missing in one dev `.env` — admin/E2E admin tests skip until set.
- Docker not installed on one Windows dev box (Postgres via other means).
- Commit `frontend/images/mesencsi-bg.jpg` to git if not already (avoid 404 on fresh clone).

---

## 4. Start here tomorrow (15 minutes)

```powershell
# Terminal 1 — backend
cd backend
.\run.bat

# Terminal 2 — checks
cd backend
.\scripts\gate_pytest.ps1
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/payments/barion/status
```

Open in browser:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/admin/login (owner password from your `.env`)

Check `.env` has at least:

- `USER_JWT_SECRET`
- `ADMIN_JWT_SECRET`
- `POSTGRES_*`
- `BARION_ENV=sandbox`
- `BARION_POS_KEY` + `BARION_PAYEE_EMAIL` (for real sandbox pay)

---

## 5. Recommended work order

| Order | Task | Done when |
|-------|------|-----------|
| 1 | `gate_pytest.ps1` green | All tests pass |
| 2 | Fix local `.env` (especially admin JWT) | Admin login works |
| 3 | Manual storefront + admin smoke | [REVIEW_CHECKLIST](REVIEW_CHECKLIST.md) A–D, F |
| 4 | Barion sandbox full flow | [BARION_SANDBOX_TESTING](BARION_SANDBOX_TESTING.md) checklist |
| 5 | SMTP + emails | Verify + paid confirmation received |
| 6 | `npm test` in `e2e/` | Playwright green |
| 7 | `gate_full.ps1` | pytest + E2E |
| 8 | Production planning | [deploy_readiness](backend/docs/deploy_readiness.md) |

---

## 6. Architecture reminder (where to edit)

| Change | Look in |
|--------|---------|
| Shop API routes | `backend/mesencsi.py`, `backend/routers/` |
| Barion | `backend/routers/payments_barion.py`, `backend/barion_api.py` |
| Admin API | `backend/admin_routes.py` |
| Storefront UI | `frontend/app.js`, `frontend/mesencsi.html`, `frontend/style.css` |
| Admin UI | `frontend/admin.html` |
| DB models | `backend/db_models.py` + Alembic `backend/alembic/versions/` |
| Tests | `backend/tests/` |
| E2E | `e2e/tests/` |

**Do not change without product sign-off:** rules for `paid`, admin payment_status, Barion verify-only path.

---

## 7. Open questions / watch list

- Is `mesencsi-bg.jpg` committed in git on the main branch?
- Was a full Barion sandbox payment signed off with `payment_status=paid` in DB?
- Which host will run production (Render, VPS, other) — drives media + env URLs?
- Hungarian vs English user-facing errors — storefront is HU; docs are EN.

---

## 8. Session notes (why things look “almost done”)

Work in recent sessions focused on **release hygiene**, not new features:

- Test gaps filled (pytest integration tests).
- Payment/email/UX polish and background asset path.
- Final cleanup: news verify guard, IPN `sync_failed`, admin dead routes.
- Playwright E2E layer + Gate scripts + English docs.
- Barion sandbox testing plan written; **execution** left to humans.

**No large refactors** were started. **Payment paid-state rules** were intentionally not changed.

---

## 9. Doc map (which file when)

| I need to… | Open |
|------------|------|
| Continue coding tomorrow | **This file** |
| Onboard a reviewer | [HANDOVER.md](HANDOVER.md) |
| Grade / accept delivery | [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md) |
| Test Barion | [BARION_SANDBOX_TESTING.md](BARION_SANDBOX_TESTING.md) |
| Run E2E / gates | [E2E_TESTING.md](E2E_TESTING.md) |
| Deploy live | [backend/docs/deploy_readiness.md](backend/docs/deploy_readiness.md) |
| Graph-ID / roadmap snapshot | [GRAPH_ID_STATUS.md](GRAPH_ID_STATUS.md) |
| Start backend only | [backend/README.md](backend/README.md) |

---

## 10. Handoff line for the next person

> Code and automated backend tests are ready. Run `gate_pytest`, then manual Barion sandbox + SMTP QA, then `e2e/npm test` and `gate_full`. Production needs HTTPS, live Barion, and upload storage — see deploy_readiness.
