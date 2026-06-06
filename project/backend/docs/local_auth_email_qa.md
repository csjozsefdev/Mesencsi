# Local QA — email verification and password reset

Shop auth uses real SMTP when `MESENCSI_PRODUCTION=true`. When `MESENCSI_PRODUCTION=false`, registration/resend/forgot still succeed if SMTP fails; verification/reset links are printed in the uvicorn terminal (`LOCAL DEV AUTH EMAIL`).

With Resend/Gmail configured, set `MESENCSI_DEV_LOG_AUTH_EMAIL_LINKS=true` in `backend/.env` so links are **also** printed when SMTP send succeeds (local QA only).

**Resend setup:** [resend_smtp.md](resend_smtp.md) — `python scripts/apply_resend_smtp_env.py` after setting `RESEND_API_KEY` and `RESEND_FROM`.

**Storefront JS modules** (`mesencsi.html` script order): `storybook-reader.js` → `js/ns.js` → `js/storage.js` → `js/dom-utils.js` → `js/api.js` → `js/validate-address.js` → `app.js`.

Locally you can use **Mailpit**, a **relay** (Gmail), or **log-only** mode (links in the uvicorn terminal).

## SMTP modes

| Mode | `.env` | Where to get links |
|------|--------|-------------------|
| Log-only | Leave `SMTP_HOST` unset (do not use placeholder `smtp.example.com`) | Uvicorn log: `LOCAL DEV AUTH EMAIL` (verification or reset link lines) |
| Mailpit | `SMTP_HOST=127.0.0.1`, `SMTP_PORT=1025`, `SMTP_USE_TLS=0`, `SMTP_FROM=noreply@localhost` | http://127.0.0.1:8025 |
| Relay | Full Gmail/Render vars (`SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, …) | Real inbox |

### Brevo: SMTP succeeds but inbox empty

If uvicorn shows `send_ok=true` but Gmail never receives the mail:

1. **Do not** set `SMTP_FROM` to your `@smtp-brevo.com` login — that is only for `SMTP_USER`.
2. In Brevo: **Senders, Domains & IPs** → add sender → verify the 6-digit code.
3. Set `SMTP_FROM=` to that verified address (e.g. `noreply@yourdomain.hu`).
4. Check **Transactional → Email** in Brevo for *blocked* / *invalid sender* on the attempt.
5. Until fixed, use the `LOCAL DEV AUTH EMAIL` reset/verify link in the uvicorn log.

Start Mailpit:

```bash
docker compose -f backend/docker-compose.yml up -d mailpit
```

Check config (local only): `GET http://127.0.0.1:8000/dev/smtp-config`

Set `FRONTEND_BASE_URL=http://127.0.0.1:8000` so links in emails match your storefront.

**Warning:** A partial SMTP block (host set but missing password) used to break dev fallback. With the repair, links are still logged in dev — but prefer Mailpit or unset `SMTP_HOST` for clarity.

## Manual QA checklist

1. **Register** a new email on the storefront → 201, message about checking email (or dev log warning).
2. **Verification link** — from Mailpit or server log (`/?email_verify_token=...` or `GET /auth/verify-email?token=...`).
3. Open link → “E-mail cím megerősítve” on login area.
4. **Login** with that email/password → `GET /auth/me` shows `email_verified_at`.
5. **Logout** works.
6. **Resend** (logged in, unverified user): Fiók → Fiók adatok → “Új megerősítő e-mail” → 200 (dev: check log again).
7. **Forgot password** → `/forgot-password.html` → generic success message.
8. **Reset link** from Mailpit or log → `/reset-password.html?token=...` → set new password.
9. **Login** with new password succeeds; old password fails.
10. **Invalid reset token** → clean 400 error on the reset page.
11. Browser console: no auth/CSRF errors on these flows.

## Optional workaround

[`scripts/dev_seed_qa_shop_user.py`](../scripts/dev_seed_qa_shop_user.py) creates a pre-verified local user — use only when you need a known account; the flows above are the real fix.

## Related

- [local_dev_cleanup.md](local_dev_cleanup.md) — removing test users
- [render_smtp.md](render_smtp.md) — hosted SMTP on Render
