# Mesencsi — Review Checklist (English)

Short pass/fail list for acceptance or grading reviews.  
Tick each item; note the date and reviewer name.

---

## A. Repository & setup

- [ ] `backend/.env.example` exists; secrets are not in git
- [ ] `backend/run.bat` starts server on port 8000
- [ ] `alembic upgrade head` runs without error
- [ ] `frontend/images/mesencsi-bg.jpg` exists (page background)

---

## B. Automated gate

- [ ] `backend\scripts\gate_pytest.ps1` → all tests pass (skips OK)
- [ ] `GET http://127.0.0.1:8000/health` → 200
- [ ] `GET http://127.0.0.1:8000/` → storefront loads
- [ ] `GET http://127.0.0.1:8000/admin/login` → admin login loads

---

## C. Auth & access control

- [ ] Guest cannot see shop/cart nav (logged-out UI)
- [ ] Verified user can log in and see webshop + cart
- [ ] Unverified user cannot place order (403)
- [ ] Unverified user cannot post news comment (403)
- [ ] Shop JWT does not work on `/admin/*`
- [ ] Admin JWT required for `/admin/orders`

---

## D. Shop & orders

- [ ] Products load in webshop (logged in)
- [ ] Cart accepts items (if products exist in DB)
- [ ] Order created with `payment_status = pending`

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

---

## G. Content (smoke)

- [ ] Gallery page loads
- [ ] News/hero area loads on homepage
- [ ] Admin can open news module (owner)
- [ ] Storybook public list or editor reachable (if content exists)

---

## H. E2E (optional but recommended)

- [ ] Node.js installed
- [ ] `cd e2e && npm test` passes (backend running)
- [ ] See [E2E_TESTING.md](E2E_TESTING.md)

---

## I. Production (out of scope for code-only handover)

- [ ] HTTPS + public URLs for Barion return/IPN
- [ ] `MESENCSI_PRODUCTION=true` + full env
- [ ] SMTP works in target environment
- [ ] Upload/media persistence planned (disk or S3)
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
