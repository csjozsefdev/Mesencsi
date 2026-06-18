# Architecture

Developer handbook for the Mesencsi backend. Use this to find the right file, trace a request, or add a feature without breaking business rules.

**Related:** [API.md](./API.md) (endpoints) · [ENVIRONMENT.md](./ENVIRONMENT.md) (env vars) · [DEVELOPMENT.md](./DEVELOPMENT.md) (local setup)

---

## Mental model

One FastAPI app (`uvicorn mesencsi:app`) serves three things on the same port in dev:

| Layer | Serves | Path |
|-------|--------|------|
| JSON API | Shop, auth, payments, admin | `/auth`, `/orders`, `/admin/...` |
| HTML shells | Storefront + admin UI | `/`, `/admin`, `/aszf` |
| Uploaded media | Admin uploads | `/media/uploads/...` |

PostgreSQL holds all state. Barion is the payment authority. SMTP + `email_outbox` handle transactional email.

```
┌─────────────┐     ┌──────────────────────────────────────┐
│  frontend/  │────▶│  mesencsi.py  +  routers/            │
│  (static)   │     │  middleware → handlers → services    │
└─────────────┘     └──────────┬───────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
         PostgreSQL        Barion API       SMTP / outbox
```

---

## Two layers of models

| File | Type | Use |
|------|------|-----|
| `db_models.py` | SQLAlchemy ORM | Database tables, relationships, queries |
| `models.py` | Pydantic | Request/response validation, API schemas |

**Rule:** Routers accept/return Pydantic (`models.py`). Services and DB code use ORM rows (`db_models.py`). Convert with `from_attributes=True` on response models.

---

## Entry point: `mesencsi.py`

### Startup (`lifespan`, ~line 218)

```
_configure_logging()
run_startup_config_validation()   ← fails fast in production (startup_config.py)
log_smtp_config_at_startup()
ensure_page_background_at_startup()
log_user_jwt_startup() / log_admin_auth_startup()
SELECT 1                          ← DB ping
ensure_qa_shop_user()             ← optional QA_SHOP_* bootstrap
```

### Router registration order (~line 239)

Order matters — static mounts must come **last**:

1. `include_router(...)` for all API routers
2. `@app` routes: products, orders, SPA shells, metrics
3. `app.mount("/media", StaticFiles)` — uploads
4. `app.mount("/", StaticFiles)` — frontend catch-all (`html=False`)

If a new API route returns 404 but the path looks correct, check it is registered **before** the `/` mount.

### Routes defined directly on `app` (not in `routers/`)

These are the highest-traffic shop endpoints — checkout logic lives here intentionally:

| Handler | Line area | Notes |
|---------|-----------|-------|
| `estimate_order_checkout` | ~394 | Pricing preview, no DB write |
| `create_order` | ~417 | **Main checkout** — guest + verified user |
| `get_orders` / `get_order` / `delete_order` | ~565+ | Verified user only |
| `get_products` / `get_stories` | ~369+ | Public catalog |

---

## Auth: how requests get a user

All auth dependencies are in `dependencies.py`.

### Shop user

| Dependency | When | Cookie / header |
|------------|------|-----------------|
| `get_current_app_user` | Must be logged in | `Authorization: Bearer` or `mesencsi_user_token` cookie |
| `get_optional_app_user` | Guest OK | Same sources; returns `None` if missing/invalid |
| `require_email_verified_shop_user` | Orders list, storybooks | Wraps `get_current_app_user` + checks `email_verified_at` |

Token validation checks `users.token_version` against JWT `tv` claim. Mismatch → 401.

**Bump `token_version` when:** password reset, ban, admin verify, account delete.

### Admin

| Dependency | When |
|------------|------|
| `get_current_admin` | Any admin route |
| `require_role(["owner"])` | Sensitive ops (ban, delete, payment_status) |
| `require_role(["owner", "maintenance"])` | Read + most writes |

Admin creds are **env-only** (`OWNER_*`, `MAINTENANCE_*`), decoded in `auth.py` via `grafi_core.auth.admin_jwt`.

### CSRF (browser mutations)

`csrf.py` → `grafi_core.security.csrf`. Frontend must:

1. `GET /auth/csrf` → sets `mesencsi_csrf` cookie
2. Send `X-CSRF-Token` header on POST/PATCH/DELETE

Fails on payment retry from Rendeléseim if CSRF is missing.

---

## Router map

```
mesencsi.py
├── /health, /health/business          routers/health.py
├── /dev/*                             routers/dev_diagnostics.py (404 on hosted)
├── /internal/incidents                routers/incidents.py
├── /internal/metrics                  metrics_support.py (on app)
├── /gallery                           routers/gallery.py
├── /auth                              routers/user_auth.py
├── /users                             routers/user_mvp.py
├── /cart                              routers/cart.py
├── /payments/barion                   routers/payments_barion.py  ← payment authority
├── /news                              routers/news_public.py
├── /storybooks                        routers/storybooks_public.py
├── /shop                              routers/shop_public.py
├── /admin                             admin_routes.py
│   ├── login/logout/me                routers/admin_auth.py
│   ├── /admin/news/*                  routers/news_admin.py
│   ├── /admin/storybooks/*            routers/storybooks_admin.py
│   └── /admin/bundle-discounts/*      routers/bundle_discounts_admin.py
├── /products, /stories, /orders       mesencsi.py (direct)
└── /, /aszf, /admin, …                mesencsi.py (SPA shells)
```

**Not mounted** (exist but unwired — do not call from frontend):

- `routers/coupons_admin.py` → would be `/admin/coupons/*`
- `routers/comments_admin.py` → would be `/admin/comments/*`

Assign coupons via `POST /admin/users/{id}/discounts` in `admin_routes.py`.

---

## Checkout flow (step by step)

### 1. Estimate (no DB write)

```
POST /orders/estimate
  → estimate_order_checkout()           mesencsi.py
  → normalize_shipping_method()         shipping_methods.py
  → resolve_shipping_price_huf()        shipping_methods.py
  → compute_checkout_pricing()          bundle_discount_service.py
       └── coupon_service.py (if coupon)
```

Coupons require verified login. Guests get 403 on coupon in estimate.

### 2. Create order

```
POST /orders
  → get_optional_app_user()             dependencies.py
  → [guest] normalize_shop_email()      shop_email.py
  → [guest] lookup_guest_idempotent_orders()   guest_order_idempotency.py
  → [user]  _resolve_checkout_user()    mesencsi.py (must be verified)
  → resolve_order_shipping()            shipping_methods.py + shipping_address.py
  → compute_checkout_pricing()          bundle_discount_service.py
  → _priced_line_to_shop_order() × N    mesencsi.py (one row per line)
  → checkout_group_id = uuid4()         groups lines for Barion
  → store_*_idempotent_orders()         if Idempotency-Key header
  → [guest] issue_guest_checkout_token()  guest_checkout_tokens.py
```

**Order shape:** One `orders` row per product line. All lines in one checkout share the same `checkout_group_id`. Barion charges the **sum** of the group.

### 3. Start payment

```
POST /payments/barion/start
  → barion_start_payment()              routers/payments_barion.py
  → _classify_barion_start()            must be FULL group or 409
  → Barion Payment/Start                barion_api.py → grafi_core
  → payment_attempts row                db_models.PaymentAttempt
```

Auth: shop JWT **or** `X-Guest-Checkout-Token` header from step 2.

### 4. Mark paid (only valid path)

```
Barion IPN or return URL
  → sync_orders_payment_status_from_barion()   payments_barion.py
  → get_payment_state()                        barion_api.py
  → map_barion_status_to_payment_status()      grafi_core
  → _apply_verified_payment_status_to_orders()
  → [if paid] _clear_user_carts_after_confirmed_paid()   routers/cart.py
  → [if paid] schedule_payment_confirmation_after_paid_sync()
       └── email_outbox row                    payment_confirmation_email.py
```

**Never** set `payment_status=paid` from admin UI. Admin can set `completed` only when already `paid`.

### 5. Send confirmation email

```
cron: python scripts/process_email_outbox.py
  → process_email_outbox_batch()        email_outbox_worker.py
  → FOR UPDATE SKIP LOCKED claim
  → send_order_payment_confirmation()   email_outbound.py
  → retry with exponential backoff (max 5 attempts)
```

---

## Payment state machine

```
pending ──GetPaymentState──▶ paid
   │                           │
   ├──▶ failed                 └──▶ email_outbox queued
   └──▶ cancelled
```

`_payment_status_transition_allowed()` in `payments_barion.py` prevents illegal reversals (e.g. paid → pending).

**Stub mode:** No `BARION_POS_KEY` → fake `preview-…` payment IDs. Blocked when `MESENCSI_PRODUCTION=true`.

---

## Key modules (where logic lives)

| Change this… | Open this file |
|--------------|----------------|
| Checkout / order creation | `mesencsi.py` → `create_order`, `_compute_order_estimate` |
| Bundle / combo pricing | `bundle_discount_service.py` |
| Coupon rules | `coupon_service.py` |
| GLS tiers (2190/2790/3290) | `shipping_methods.py` → `recommend_gls_shipping()` |
| Address validation | `shipping_address.py` |
| Barion API calls | `barion_api.py` → `grafi_core/payments/barion_client.py` |
| Payment sync / IPN | `routers/payments_barion.py` → `sync_orders_payment_status_from_barion()` |
| Cart persistence / clear | `routers/cart.py` |
| Shop register/login/verify | `routers/user_auth.py` |
| User profile / avatar | `routers/user_mvp.py` |
| Admin CRUD | `admin_routes.py` + `routers/*_admin.py` |
| Image upload / S3 | `image_upload.py`, `media_storage.py` |
| Email send | `email_outbound.py` |
| Email queue worker | `email_outbox_worker.py` |
| Production env validation | `startup_config.py` |
| Rate limits | `auth_limits.py` (set `REDIS_URL` for multi-worker) |
| CORS dev origins | `cors_config.py` |
| DB connection | `database.py` |
| Pydantic schemas | `models.py` |
| ORM tables | `db_models.py` |

---

## Database essentials

### Orders are line-based

```
checkout_group_id: "abc-123"
├── order id=1  product=A  qty=2  total_price=…
├── order id=2  product=B  qty=1  total_price=…
└── payment_attempts.checkout_group_id = "abc-123"
```

Query all lines in a checkout: `WHERE checkout_group_id = ?`.

### Important columns on `orders`

| Column | Meaning |
|--------|---------|
| `user_id` | `NULL` = guest order |
| `checkout_group_id` | Groups lines for one checkout |
| `payment_status` | `pending` / `paid` / `failed` / `cancelled` |
| `barion_payment_id` | Set after Payment/Start |
| `shipping_method` | `personal_pickup` or `gls_home` |
| `shipping_price` | Fee in HUF (on every line in group) |
| `shipping_metadata_json` | GLS address JSON |

### Admin auth is not in DB

Owner/maintenance passwords are bcrypt hashes in `.env`. Generate with:

```bash
python scripts/setup_admin_credentials.py
```

---

## `grafi_core/` — shared library

Reusable code extracted for potential reuse across projects. Mesencsi wraps it with project-specific settings:

| Mesencsi file | grafi_core module |
|---------------|-------------------|
| `user_tokens.py` | `grafi_core.auth.user_jwt` |
| `auth.py` | `grafi_core.auth.admin_jwt` |
| `barion_api.py` | `grafi_core.payments.barion_client` |
| `email_outbound.py` | `grafi_core.email.transport` |
| `csrf.py` | `grafi_core.security.csrf` |
| `mesencsi_settings.py` | cookie names, project flags |

`demo_backend/` is a minimal FastAPI app for grafi_core smoke tests — not the production shop.

When fixing Barion or JWT bugs, check **both** the Mesencsi wrapper and `grafi_core/`.

---

## Middleware stack

Request flows through (outer → inner):

1. **MetricsMiddleware** — `metrics_support.py`
2. **ProxyHeadersMiddleware** — `TRUSTED_PROXY_HOSTS`
3. **CsrfMiddleware** — `csrf.py`
4. **CORSMiddleware** — `cors_config.py`
5. **Security headers** — `security_headers.py`

---

## Business rules (do not break)

| # | Rule | Enforced in |
|---|------|-------------|
| 1 | Guest or verified user can checkout | `mesencsi.py` `create_order` |
| 2 | `paid` only from Barion sync | `payments_barion.py` |
| 3 | Barion start needs full checkout group | `_classify_barion_start()` → 409 |
| 4 | Admin `completed` only when `paid` | `admin_routes.py` |
| 5 | News comments: verified users only | `routers/news_public.py` |
| 6 | JWT `token_version` invalidation | `dependencies.py`, `user_tokens.py` |
| 7 | Email lowercase, login case-insensitive | `shop_email.py`, migration 025 |
| 8 | Payment email via outbox, not inline | `payment_confirmation_email.py` |
| 9 | GLS auto-tier; Foxpost rejected | `shipping_methods.py` |
| 10 | Production startup validation | `startup_config.py` |

Each rule has tests in `tests/`. Search test names before changing behaviour.

---

## Debugging guide

| Symptom | First place to look |
|---------|---------------------|
| Order created but payment 409 | `_classify_barion_start()` — partial `checkout_group_id` |
| IPN received, order still pending | `sync_orders_payment_status_from_barion()` logs; `BARION_IPN_SECRET` |
| IPN works in prod but not locally | No public HTTPS — use return URL or manual `GET .../payment/{id}/state` |
| Admin login 401 | `ADMIN_JWT_SECRET` missing; stale cookie format |
| Shop login 401 after password change | Expected — `token_version` bumped |
| Coupon not applied | `bundle_discount_service.py`; combo may override coupon |
| GLS wrong price | `count_shippable_item_quantity()` + `recommend_gls_shipping()` |
| Email not sent after payment | `email_outbox` table → run `process_email_outbox.py` |
| CSRF 403 on payment retry | Frontend missing `GET /auth/csrf` before POST |
| Upload 404 after deploy | Ephemeral disk — set `MEDIA_STORAGE=s3` or persistent volume |
| pytest passes, prod fails | `MESENCSI_PRODUCTION=true` path — run `startup_config` checks |

**Useful log events:** `barion_orders_synced`, `barion_orders_sync_idempotent`, `payment_confirmation_schedule_failed`.

**Dev endpoints (local only):**

- `GET /dev/smtp-config`
- `GET /payments/barion/status`

---

## How to add common features

### New public API endpoint

1. Add Pydantic models to `models.py`
2. Create handler in `routers/your_router.py` or `mesencsi.py` if core shop
3. Register router in `mesencsi.py` **before** static mounts
4. Add test in `tests/test_your_feature.py`
5. Document in [API.md](./API.md)

### New admin endpoint

1. Add to `admin_routes.py` or sub-router in `routers/`
2. Use `Depends(require_role(["owner"]))` for sensitive writes
3. Test in `tests/test_admin_*.py`

### New database column

1. Edit `db_models.py`
2. `alembic revision --autogenerate -m "description"`
3. Review migration — autogenerate is not always correct
4. Update Pydantic models if exposed via API
5. `alembic upgrade head` + test

### New email type

1. Add send function in `email_outbound.py` (or queue via outbox pattern)
2. If durable: insert into `email_outbox`, extend `email_outbox_worker.py`
3. Test with Mailpit (`docker compose up -d`) or dev log mode

---

## Testing architecture

| Layer | Location | DB |
|-------|----------|-----|
| Integration (main) | `tests/` | SQLite in-memory per test |
| grafi_core unit | `grafi_core/tests/` | None / minimal |
| Postgres smoke | `tests/test_postgres_*.py` | Real Postgres (skipped without URL) |
| E2E | `../../e2e/` | Running server + Playwright |

`tests/conftest.py` sets `MESENCSI_TEST_DATABASE_URL=sqlite:///:memory:` and drops/recreates schema **per test**. Barion runs in stub mode unless a test sets `BARION_POS_KEY`.

```bash
.\scripts\gate_pytest.ps1          # 347 tests
pytest tests/test_cart_clear_on_payment.py -v   # single file
pytest -k "barion" -q              # by keyword
```

Route registration order is tested in `tests/test_route_registration.py` — run it if you change mounts.

---

## Static assets

| Path | Served at | Survives restart? |
|------|-----------|-------------------|
| `frontend/` | `/`, `/css/`, `/js/`, `/images/` | Yes (in git) |
| `backend/media/uploads/` | `/media/uploads/` | Only with persistent disk or S3 |
| `frontend/images/mesencsi-bg.jpg` | `/images/mesencsi-bg.jpg` | Yes — checked at startup |

Production on Render: use `MEDIA_STORAGE=s3` or mount persistent volume. See [media_persistence_smoke.md](./media_persistence_smoke.md).

---

## Deployment summary

| Environment | How |
|-------------|-----|
| Local | `docker compose up -d` + `run.bat` |
| Render | `render.yaml` — `alembic upgrade head` + uvicorn |
| Migrations | 32 revisions, head `032_storybook_page_image_layout` |

Pre-deploy: `python scripts/predeploy_alembic_check.py`  
Post-deploy cron: `python scripts/process_email_outbox.py` (every 1–5 min)

Full checklist: [deploy_readiness.md](./deploy_readiness.md) · Ops: [ops_runbook.md](./ops_runbook.md)
