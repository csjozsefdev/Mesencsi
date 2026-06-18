# API reference

Base URL: `http://127.0.0.1:8000` (dev) or your production HTTPS URL.

**OpenAPI:** `GET /docs` and `GET /redoc` (disabled when `MESENCSI_PRODUCTION=true`).

**Auth headers:**

| Context | Header |
|---------|--------|
| Shop user | `Authorization: Bearer <shop_jwt>` |
| Admin | `Authorization: Bearer <admin_jwt>` or HttpOnly cookie from `/admin/login` |
| CSRF (browser POST/PATCH/DELETE) | `X-CSRF-Token` + `mesencsi_csrf` cookie (fetch via `GET /auth/csrf`) |
| Guest payment | `X-Guest-Checkout-Token` (returned by `POST /orders` for guests) |
| Idempotency | `Idempotency-Key` on `POST /orders` (8–128 chars, `[A-Za-z0-9_-]`) |

---

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Liveness probe |
| GET | `/health/business` | Admin JWT | Deep health: DB, static frontend, media uploads |

---

## Shop config & catalog

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/shop/config` | — | Coming-soon flag, shipping methods, GLS tiers |
| GET | `/products` | — | Product list |
| GET | `/products/{id}` | — | Single product |
| GET | `/stories` | — | Tale texts for Mesék section |
| GET | `/gallery` | — | Paginated public gallery |

---

## Cart (authenticated shop user)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/cart` | Shop JWT | Get persisted cart |
| PUT | `/cart` | Shop JWT | Replace cart items |

Cart is cleared server-side after successful payment.

---

## Orders

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/orders/estimate` | Optional | Server-side pricing (bundle + coupon + shipping). Coupons require verified login |
| POST | `/orders` | Guest or verified | Create order. Guest: `customer_email` in body. Returns guest checkout token header |
| GET | `/orders` | Verified | Order history |
| GET | `/orders/{id}` | Verified | Single order |
| DELETE | `/orders/{id}` | Verified | Delete order line (guards apply) |

**Shipping methods:** `personal_pickup` (0 Ft), `gls_home` (2190/2790/3290 Ft by quantity). Foxpost rejected (422).

---

## Auth (`/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | — | Register shop account |
| POST | `/auth/login` | — | Login (case-insensitive email) |
| POST | `/auth/logout` | — | Logout |
| GET | `/auth/me` | Shop JWT | Current user |
| GET | `/auth/csrf` | — | CSRF token cookie |
| POST | `/auth/verify-email` | — | Verify email with token |
| POST | `/auth/resend-verification` | Shop JWT | Resend verification email |
| POST | `/auth/forgot-password` | — | Request password reset |
| POST | `/auth/reset-password` | — | Reset password with token |

---

## Users (`/users`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users/me` | Shop JWT | Profile |
| PATCH | `/users/me` | Shop JWT | Update profile |
| POST | `/users/me/avatar` | Shop JWT | Upload avatar |
| DELETE | `/users/me` | Shop JWT | Delete account |
| GET | `/users/me/coupons` | Shop JWT | Available coupons |

---

## News (`/news`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/news` | — | Published posts |
| GET | `/news/featured` | — | Featured post |
| GET | `/news/{slug}` | — | Single post |
| POST | `/news/{slug}/comments` | Verified | Post comment |

---

## Storybooks (`/storybooks`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/storybooks` | — | Published storybooks |
| GET | `/storybooks/{slug}` | Login required | Read storybook (purchased content) |

---

## Barion payments (`/payments/barion`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/payments/barion/status` | — | Config preview (sandbox, POS key, IPN secret) |
| POST | `/payments/barion/start` | Shop JWT or guest token | Start payment for full checkout group |
| GET | `/payments/barion/return` | — | Browser return redirect |
| GET | `/payments/barion/cancel` | — | Browser cancel redirect |
| POST | `/payments/barion/ipn` | IPN secret | Barion IPN callback |
| GET | `/payments/barion/payment/{id}/state` | Shop JWT | Manual payment state sync |
| POST | `/payments/barion/callback` | Debug secret (prod) | Internal/debug sync |
| POST | `/payments/barion/webhook` | — | Deprecated alias for callback |

**Rules:**

- `paid` status only from Barion `GetPaymentState` sync
- Partial checkout group on start → 409
- Empty `BARION_POS_KEY` → stub mode (dev only, blocked in production)

---

## Admin (`/admin`)

All admin API routes require admin JWT. Roles: `owner` (full), `maintenance` (limited).

### Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/login` | Admin login → JWT cookie |
| POST | `/admin/logout` | Clear session |
| GET | `/admin/me` | Current admin user |

### Orders

| Method | Path | Owner only | Description |
|--------|------|------------|-------------|
| GET | `/admin/orders` | — | List orders |
| PATCH | `/admin/orders/{id}` | partial | Update status (completed only when paid) |
| DELETE | `/admin/orders/{id}` | yes | Delete order line |

### Shop users

| Method | Path | Owner only | Description |
|--------|------|------------|-------------|
| GET | `/admin/shop-users` | — | List shop users |
| POST | `/admin/shop-users/{id}/verify` | yes | Manually verify email |
| POST | `/admin/shop-users/{id}/ban` | yes | Ban user |
| POST | `/admin/shop-users/{id}/unban` | yes | Unban user |
| DELETE | `/admin/shop-users/{id}` | yes | Soft-delete user |
| POST | `/admin/users/{id}/discounts` | yes | Assign personal coupon |

### Content

| Area | Prefix | Description |
|------|--------|-------------|
| Products | `/admin/products` | CRUD + image upload |
| Gallery | `/admin/gallery` | CRUD + uploads |
| Stories | `/admin/stories` | CRUD |
| News | `/admin/news` | CRUD, publish, feature, images |
| Storybooks | `/admin/storybooks` | Full CMS (pages, audio, layout) |
| Bundle discounts | `/admin/bundle-discounts` | Combo pricing rules |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/system` | System counts (maintenance+) |
| GET | `/admin/logs` | Recent log entries |

---

## Internal / dev

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/internal/metrics` | `X-Metrics-Token` | Prometheus-style metrics |
| GET | `/internal/incidents` | `X-Incidents-Token` | Error incident log |
| GET | `/dev/smtp-config` | — | SMTP diagnostics (404 on hosted) |
| GET | `/dev/smtp-credential-proof` | — | SMTP login proof (404 on hosted) |

---

## HTML pages (not JSON)

| Path | File |
|------|------|
| `/`, `/mesencsi.html` | Storefront |
| `/aszf`, `/adatkezeles`, `/impresszum` | Legal SPA routes |
| `/admin/login` | Admin login |
| `/admin`, `/admin/dashboard` | Admin dashboard |

Static assets: `/css/`, `/js/`, `/images/`, `/media/uploads/`.

---

## Error codes (common)

| Code | Meaning |
|------|---------|
| 401 | Missing or invalid JWT |
| 403 | Forbidden (unverified user, wrong role, CSRF fail) |
| 409 | Conflict (idempotency mismatch, partial checkout group) |
| 422 | Validation error |
| 429 | Rate limit exceeded |
