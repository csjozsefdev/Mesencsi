# Render deployment — SMTP for confirmation emails

Registration and resend-verification require outbound SMTP on any **hosted** deploy (Render, staging, or `MESENCSI_PRODUCTION=true`). Without these variables the app **fails startup** or returns **503** when sending mail — confirmation is not silently skipped.

## Required environment variables (Render dashboard)

Set these on the **Web Service → Environment** tab (use your provider’s SMTP credentials, e.g. SendGrid, Mailgun, Brevo, or your host’s relay):

| Variable | Example | Notes |
|----------|---------|--------|
| `SMTP_HOST` | `smtp.sendgrid.net` | Relay hostname |
| `SMTP_PORT` | `587` | Usually `587` (STARTTLS) or `465` (SSL) |
| `SMTP_USE_TLS` | `1` | Set `0` only for plain SMTP (e.g. local Mailpit) |
| `SMTP_USER` | `apikey` | SMTP login user |
| `SMTP_PASSWORD` | *(secret)* | SMTP password — never log or commit |
| `SMTP_FROM` | `noreply@your-domain.hu` | From address (must be allowed by your provider) |

Also set public URLs used in email links:

| Variable | Example |
|----------|---------|
| `FRONTEND_BASE_URL` | `https://your-shop.onrender.com` |
| `PUBLIC_SITE_URL` | Same as storefront origin if single host |
| `BACKEND_PUBLIC_URL` | `https://your-api.onrender.com` if API is on a separate host |

## Hosted detection (no extra flag required on Render)

The server treats the deploy as **hosted** when any of these is true:

- `RENDER=true` (set automatically on Render.com)
- `ENVIRONMENT=staging` | `production` | `prod` | `live`
- `MESENCSI_PRODUCTION=true`

Hosted startup requires `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM`.

## Local development

- Copy `.env.example` → `.env` (`.env` is gitignored).
- Leave `SMTP_HOST` empty: verification **links are logged** instead of emailed.
- Optional Mailpit: `docker compose up -d`, then `SMTP_HOST=127.0.0.1`, `SMTP_PORT=1025`, `SMTP_USE_TLS=0`, UI at `http://127.0.0.1:8025`.

## Staging QA shop user (optional)

To avoid manual email verification during checkout/Barion QA on staging:

```
QA_SHOP_EMAIL=qa-shop@your-staging-domain.hu
QA_SHOP_PASSWORD=<plain or bcrypt hash>
```

On startup the app ensures this `AppUser` exists with `email_verified_at` set and `is_active=true`.

**Admin panel** logins (`OWNER_*` / `MAINTENANCE_*`) are separate env-based accounts and do not require shop email verification.

Manual verify for an existing shop user (any environment with DB access):

```bash
python scripts/dev_manual_verify_shop_user.py "user@example.com"
```

## Troubleshooting

1. Check Render logs for `startup_config_error` — missing SMTP prevents boot on hosted.
2. After register, look for `Verification email sent successfully` or `SMTP send failed` with `error_type=` (passwords are never logged).
3. `POST /auth/resend-verification` returns **503** if SMTP is missing or send fails (same policy as register on hosted).

See also: [deploy_readiness.md](./deploy_readiness.md) (full production checklist).
