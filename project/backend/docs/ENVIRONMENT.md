# Environment variables

Copy `backend/.env.example` to `backend/.env`. Never commit `.env`.

**Load order:** `.env` → optional `.env.py` (same `KEY=value` syntax, via `env_loader.py`).

---

## Production flag

| Variable | Default | Purpose |
|----------|---------|---------|
| `MESENCSI_PRODUCTION` | empty | `true` → strict production rules: no Barion stub, no OpenAPI docs, IPN secret required, SMTP required, HTTPS URLs |
| `MESENCSI_INTERNAL_DEBUG_SECRET` | empty | Optional header for `POST /payments/barion/callback` in production |
| `ENVIRONMENT` | `development` | Shown in `GET /health` (`development`, `staging`, `production`) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`) |
| `MESENCSI_LOG_LEVEL` | — | Alias for `LOG_LEVEL` |
| `RENDER` | auto on Render | Triggers hosted SMTP requirements |

---

## Shop UX

| Variable | Default | Purpose |
|----------|---------|---------|
| `SHOP_PRODUCTS_COMING_SOON` | `false` | `true` → shop shows "coming soon" placeholder (`GET /shop/config`) |
| `SHOP_PRODUCTS_COMING_SOON_MESSAGE` | — | Custom Hungarian message |

---

## PostgreSQL

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_USER` | `mesencsi` | Database user |
| `POSTGRES_PASSWORD` | — | **Required** |
| `POSTGRES_HOST` | `localhost` | Host |
| `POSTGRES_PORT` | `5432` | Port |
| `POSTGRES_DB` | `mesencsi` | Database name |

**Test only:**

| Variable | Purpose |
|----------|---------|
| `MESENCSI_TEST_DATABASE_URL` | Pytest SQLite/Postgres override |
| `MESENCSI_POSTGRES_SMOKE_URL` | Optional Postgres smoke tests |

---

## Shop user JWT

| Variable | Default | Purpose |
|----------|---------|---------|
| `USER_JWT_SECRET` | — | **Required.** Min 32 chars, not placeholder |
| `JWT_ALGORITHM` | `HS256` | `HS256` / `HS384` / `HS512` |
| `JWT_EXPIRE_MINUTES` | — | Short-lived override |
| `USER_JWT_EXPIRE_DAYS` | `7` | Shop session length |

---

## Admin JWT & credentials

| Variable | Default | Purpose |
|----------|---------|---------|
| `ADMIN_JWT_SECRET` | — | **Required.** Separate from shop JWT, min 32 chars |
| `ADMIN_JWT_EXPIRE_HOURS` | `12` | Admin session length |
| `ADMIN_JWT_EXPIRE_MINUTES` | — | Overrides hours if set |
| `ADMIN_JWT_ALGORITHM` | `HS256` | Algorithm |
| `OWNER_USERNAME` | `owner` | Admin owner login |
| `OWNER_PASSWORD` | bcrypt hash | Generate: `python scripts/setup_admin_credentials.py` |
| `MAINTENANCE_USERNAME` | `maint` | Maintenance admin login |
| `MAINTENANCE_PASSWORD` | bcrypt hash | Limited write access |

---

## Barion payments

| Variable | Default | Purpose |
|----------|---------|---------|
| `BARION_ENV` | `sandbox` | `sandbox` or `production` (aliases: `prod`, `live`, `release`) |
| `BARION_SANDBOX` | — | Legacy alias if `BARION_ENV` empty |
| `BARION_POS_KEY` | empty | Barion POS key. Empty = dev stub only |
| `BARION_PAYEE_EMAIL` | — | Payee for Payment/Start |
| `BARION_API_BASE_URL` | auto | Override API host |
| `BARION_GATEWAY_URL` | auto | Override gateway URL |
| `BARION_BACKEND_PUBLIC_URL` | `http://127.0.0.1:8000` | Base for return/IPN URL building |
| `BARION_RETURN_URL` | auto | Full HTTPS return URL |
| `BARION_CALLBACK_URL` | auto | IPN callback URL |
| `BARION_IPN_URL` | — | Alias for callback URL |
| `BARION_IPN_SECRET` | — | **Required in production.** IPN authentication |
| `BARION_CANCEL_URL` | auto | Cancel redirect |
| `BARION_FRONTEND_LANDING_URL` | — | Post-payment storefront redirect |
| `BARION_PAYMENT_WINDOW` | `01:00:00` | Payment expiry |
| `BARION_LOCALE` | `hu-HU` | Barion locale |
| `BARION_CURRENCY` | `HUF` | Currency |
| `BARION_POS_ID` | — | Rare stub live-path check |
| `BARION_PIXEL_ID` | — | Base Pixel ID (`BP-XXXXXXXXXX-XX`) — injected into public HTML only; never logged |

---

## SMTP & public URLs

| Variable | Default | Purpose |
|----------|---------|---------|
| `SMTP_HOST` | — | SMTP relay host |
| `SMTP_PORT` | `587` | Port |
| `SMTP_USE_TLS` | `1` | TLS enabled |
| `SMTP_USER` | — | SMTP username |
| `SMTP_PASSWORD` | — | SMTP password / API key |
| `SMTP_FROM` | — | From address (must be verified with provider) |
| `FRONTEND_BASE_URL` | `http://127.0.0.1:8000` | Links in emails |
| `PUBLIC_SITE_URL` | `http://127.0.0.1:8000` | Public site URL |
| `BACKEND_PUBLIC_URL` | `http://127.0.0.1:8000` | Backend public URL |
| `ORDER_CONFIRMATION_PROCESSING_NOTE` | — | Extra text in payment confirmation email |
| `MESENCSI_DEV_LOG_AUTH_EMAIL_LINKS` | `false` | Log verify/reset links locally even when SMTP works |

**Resend helper vars** (used by `scripts/apply_resend_smtp_env.py`):

| Variable | Purpose |
|----------|---------|
| `RESEND_API_KEY` | Resend API key |
| `RESEND_FROM` | Verified sender address |

See [resend_smtp.md](./resend_smtp.md) and [render_smtp.md](./render_smtp.md).

---

## CORS

| Variable | Default | Purpose |
|----------|---------|---------|
| `CORS_ALLOWED_ORIGINS` | localhost (dev) | Comma-separated origins. **Required in production** |
| `ALLOWED_ORIGINS` | — | Alias for `CORS_ALLOWED_ORIGINS` |

Dev defaults include Vite (`5173`) and Live Server (`5500`) — see `cors_config.py`.

---

## Media storage

| Variable | Default | Purpose |
|----------|---------|---------|
| `MEDIA_STORAGE` | `local` | `local` or `s3` |
| `MEDIA_PUBLIC_BASE_URL` | — | CDN base URL when `MEDIA_STORAGE=s3` |
| `S3_BUCKET` | — | S3 bucket name |
| `S3_ENDPOINT_URL` | — | S3-compatible endpoint (R2, MinIO, etc.) |
| `S3_REGION` | — | AWS region |
| `S3_KEY_PREFIX` | — | Optional key prefix |

Local mode stores files in `backend/media/uploads/`.

---

## Rate limiting & proxy

| Variable | Default | Purpose |
|----------|---------|---------|
| `REDIS_URL` | — | Shared rate limits across workers (e.g. `redis://127.0.0.1:6379/0`) |
| `TRUSTED_PROXY_HOSTS` | `127.0.0.1` | Comma-separated IPs for `X-Forwarded-*` trust |

---

## Internal ops

| Variable | Default | Purpose |
|----------|---------|---------|
| `INCIDENTS_READ_TOKEN` | — | Protects `GET /internal/incidents` (`X-Incidents-Token`) |
| `METRICS_READ_TOKEN` | — | Protects `GET /internal/metrics` (`X-Metrics-Token`) |
| `MESENCSI_PROTECTED_SHOP_EMAILS` | — | Emails protected from admin delete/ban |

---

## QA / staging only

| Variable | Purpose |
|----------|---------|
| `QA_SHOP_EMAIL` | Pre-verified shop user email (blocked in production) |
| `QA_SHOP_PASSWORD` | Plain or bcrypt password for QA user |

**Blocked when `MESENCSI_PRODUCTION=true`.**

---

## Production validation

When `MESENCSI_PRODUCTION=true`, `startup_config.py` enforces:

- Distinct `USER_JWT_SECRET` and `ADMIN_JWT_SECRET` (min 32 chars, not placeholders)
- Real bcrypt hashes for admin passwords (not `.env.example` defaults)
- `CORS_ALLOWED_ORIGINS` without wildcard or localhost
- HTTPS on `PUBLIC_SITE_URL`, `BACKEND_PUBLIC_URL`, `FRONTEND_BASE_URL`
- Full SMTP configuration
- `BARION_IPN_SECRET` set
- No `QA_SHOP_*` variables

Failure → `StartupConfigError`, app does not start.

Full checklist: [deploy_readiness.md](./deploy_readiness.md).
