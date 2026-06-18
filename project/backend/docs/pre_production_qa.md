# Pre-production QA — owner checklist

Use this with [deploy_readiness.md](./deploy_readiness.md) §9, [BARION_SANDBOX_TESTING.md](../../BARION_SANDBOX_TESTING.md), and [REVIEW_CHECKLIST.md](../../REVIEW_CHECKLIST.md).

**Not in scope here (external):** SMTP provider/domain, Barion merchant/POS registration, shipping fee policy, carrier APIs, legal pages ([production_legal_todo.md](./production_legal_todo.md)).

---

## Before you start

- [ ] `python scripts/predeploy_alembic_check.py` → ok (exit 0)
- [ ] `alembic upgrade head` — head revision **`032_storybook_page_image_layout`**
- [ ] `payment_attempts` and `email_outbox` tables exist
- [ ] Production-like env: `MESENCSI_PRODUCTION=true`, distinct JWT secrets, `BARION_IPN_SECRET`, SMTP, CORS
- [ ] Admin passwords are **not** the `.env.example` placeholder bcrypt hashes
- [ ] `GET /health` → 200
- [ ] `GET /health/business` (admin JWT) → `static_frontend.ok`, `media_uploads.ok`
- [ ] Automated gate: `pytest -q` → 347 passed (skips OK)

---

## Shop — guest (no account)

- [ ] Browse webshop and add to cart without login
- [ ] Checkout: name, email, phone, shipping method, GLS address if needed
- [ ] Barion sandbox payment → return → order `payment_status=paid`
- [ ] Optional post-purchase account offer (dismiss OK)
- [ ] Confirmation email shows shipping method, fee, delivery address (GLS)

## Shop — verified user

- [ ] Register → verify email (SMTP or dev log) → login
- [ ] Login works with different email casing (e.g. `User@Mail.com` vs stored lowercase)
- [ ] Profile: save shipping address, pick preset avatar, upload avatar
- [ ] Webshop: add to cart, change quantity, apply coupon (if any)
- [ ] Checkout: linear flow, bottom order summary, **Rendelés elküldése**
- [ ] Personal pickup 0 Ft; GLS tiers 2190 / 2790 / 3290 Ft by quantity
- [ ] GLS: optional recipient name; simplified address (no country field)
- [ ] Repeat checkout with same `Idempotency-Key` header → same order group (no duplicate charge path)
- [ ] Barion payment (sandbox or live) → return URL → `payment_status=paid`
- [ ] `email_outbox` row created; cron/script sends payment confirmation email
- [ ] Fiók → Rendeléseim: order visible, shipping + notes shown, payment retry works (CSRF)
- [ ] Password reset → old JWT no longer works (token_version bump)
- [ ] Logout / login again — session and cart behave as expected

---

## Admin

- [ ] `/admin/login` — owner and maintenance roles
- [ ] Orders: list, shipping details, status change (`completed` only when paid)
- [ ] **Maintenance** cannot change `payment_status` (403)
- [ ] **Owner** can verify/ban/unban/delete shop users; maintenance cannot
- [ ] Cannot set `paid` manually; Barion-linked payment readonly
- [ ] Products / news / gallery / storybook save (owner)
- [ ] Shop users: verify, ban, personal coupon (owner)

---

## Security smoke

- [ ] `GET /admin/shop-users` without token → 401
- [ ] Unverified logged-in user cannot `POST /orders` or post news comment
- [ ] Shop JWT with stale `token_version` → 401
- [ ] `POST /payments/barion/start` with incomplete checkout group → 409
- [ ] Public staging (if any): `BARION_IPN_SECRET` set or IPN blocked — never open IPN on internet without secret

---

## Automated gates (developers)

```bash
cd backend
python scripts/predeploy_alembic_check.py
python -m alembic upgrade head
python -m pytest -q
# optional Postgres:
python scripts/postgres_smoke.py
# optional E2E:
cd ../e2e && npm test
```

---

## Sign-off

| Role | Name | Date | Environment |
|------|------|------|-------------|
| Owner | | | |
| Dev | | | |
