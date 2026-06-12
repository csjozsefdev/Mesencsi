# Mesencsi — Review Checklist (English)

Short pass/fail list for acceptance or grading reviews.  
Tick each item; note the date and reviewer name.

**Alembic head:** `029` · **Tests:** ~300 pytest (SQLite); optional Postgres smoke.

---

## A. Repository & setup

- [ ] `backend/.env.example` exists; secrets are not in git
- [ ] `backend/run.bat` starts server on port 8000
- [ ] `python scripts/predeploy_alembic_check.py` → ok
- [ ] `alembic upgrade head` runs without error (head `029`)
- [ ] `frontend/images/mesencsi-bg.jpg` exists (page background)

---

## B. Automated gate

- [ ] `backend\scripts\gate_pytest.ps1` → ~300 tests pass (skips OK)
- [ ] `GET http://127.0.0.1:8000/health` → 200
- [ ] `GET http://127.0.0.1:8000/` → storefront loads
- [ ] `GET http://127.0.0.1:8000/admin/login` → admin login loads

---

## C. Auth & access control

- [ ] Guest cannot see shop/cart nav (logged-out UI)
- [ ] Verified user can log in and see webshop + cart
- [ ] Email login is case-insensitive
- [ ] Unverified user cannot place order (403)
- [ ] Unverified user cannot post news comment (403)
- [ ] Shop JWT does not work on `/admin/*`
- [ ] Admin JWT required for `/admin/orders`
- [ ] Password reset invalidates previous shop JWT (token_version)

---

## D. Shop & orders

- [ ] Products load in webshop (logged in)
- [ ] Cart accepts items (if products exist in DB)
- [ ] Order created with `payment_status = pending`
- [ ] Duplicate `POST /orders` with same `Idempotency-Key` does not create duplicate group

---

## E. Barion (sandbox only)

- [ ] `BARION_ENV=sandbox` (not production)
- [ ] `GET /payments/barion/status` → `sandbox: true`, `rest_api_enabled: true`
- [ ] Payment start redirects to `secure.test.barion.com`
- [ ] Successful sandbox payment → order `payment_status = paid`
- [ ] Failed/cancelled payment → order **not** `paid`
- [ ] Details: [BARION_SANDBOX_TESTING.md](BARION_SANDBOX_TESTING.md)

---

## F. Admin

- [ ] Owner can log in to `/admin`
- [ ] Orders list shows payment status
- [ ] Cannot set `completed` on unpaid order
- [ ] Cannot set `paid` manually from admin
- [ ] Maintenance cannot change `payment_status` (owner only)
- [ ] Shop user verify/ban/delete is owner-only

---

## G. Content (smoke)

- [ ] Gallery page loads
- [ ] News/hero area loads on homepage
- [ ] Admin can open news module (owner)
- [ ] Storybook public list or editor reachable (if content exists)
- [ ] Storybook text drag works in admin editor

---

## H. E2E (optional but recommended)

- [ ] Node.js installed
- [ ] `cd e2e && npm test` passes (backend running)
- [ ] See [E2E_TESTING.md](E2E_TESTING.md)

---

## I. Pre-production sign-off (owner)

- [ ] Full walkthrough: [backend/docs/pre_production_qa.md](backend/docs/pre_production_qa.md)
- [ ] Deploy env: [backend/docs/deploy_readiness.md](backend/docs/deploy_readiness.md)
- [ ] Ops (outbox cron): [backend/docs/ops_runbook.md](backend/docs/ops_runbook.md)

---

## J. Production (out of scope for code-only handover)

- [ ] HTTPS + public URLs for Barion return/IPN
- [ ] `MESENCSI_PRODUCTION=true` + full env
- [ ] SMTP works in target environment
- [ ] `process_email_outbox.py` scheduled (cron / Render job)
- [ ] Upload/media persistence planned (disk or S3)
- [ ] Legal pages approved — [production_legal_todo.md](backend/docs/production_legal_todo.md)
- [ ] See [backend/docs/deploy_readiness.md](backend/docs/deploy_readiness.md)

---

## Result

| Field | Value |
|-------|--------|
| Reviewer | |
| Date | |
| **Code handover** | PASS / FAIL |
| **Release ready** | PASS / FAIL |
| Notes | |
