# Pre-production QA — owner checklist

Use this with [deploy_readiness.md](./deploy_readiness.md) §9, [BARION_SANDBOX_TESTING.md](../../BARION_SANDBOX_TESTING.md), and [REVIEW_CHECKLIST.md](../../REVIEW_CHECKLIST.md).

**Not in scope here (external):** SMTP provider/domain, Barion merchant/POS registration, shipping fee policy, carrier APIs.

---

## Before you start

- [ ] `alembic upgrade head` — head revision **`024_password_reset_tokens`**
- [ ] `payment_attempts` table exists (required for Barion retry)
- [ ] Production-like env: `MESENCSI_PRODUCTION=true`, real JWT secrets, `BARION_IPN_SECRET`, SMTP, CORS
- [ ] Admin passwords are **not** the `.env.example` defaults
- [ ] `GET /health` → 200
- [ ] `GET /health/business` (admin JWT) → `static_frontend.ok`, `media_uploads.ok`

---

## Shop (verified user)

- [ ] Register → verify email (SMTP or dev log) → login
- [ ] Profile: save shipping address, pick preset avatar, upload avatar
- [ ] Webshop: add to cart, change quantity, apply coupon (if any)
- [ ] Checkout: full address, notes, confirm → order created
- [ ] Barion payment (sandbox or live) → return URL → `payment_status=paid`
- [ ] Payment confirmation email (if SMTP configured)
- [ ] Fiók → Rendeléseim: order visible, shipping + notes shown, payment retry works (CSRF)
- [ ] Logout / login again — session and cart behave as expected

---

## Admin

- [ ] `/admin/login` — owner and maintenance roles
- [ ] Orders: list, shipping details, status change (`completed` only when paid)
- [ ] Cannot set `paid` manually; Barion-linked payment readonly
- [ ] Products / news / gallery / storybook save (owner)
- [ ] Shop users: verify, ban, personal coupon

---

## Security smoke

- [ ] `GET /admin/shop-users` without token → 401
- [ ] Unverified user cannot `POST /orders` or post news comment
- [ ] Public staging (if any): `BARION_IPN_SECRET` set or IPN blocked — never open IPN on internet without secret

---

## Automated gates (developers)

```bash
cd backend
python -m pytest -q
# optional:
cd ../e2e && npm test
```

---

## Sign-off

| Role | Name | Date | Environment |
|------|------|------|-------------|
| Owner | | | |
| Dev | | | |
