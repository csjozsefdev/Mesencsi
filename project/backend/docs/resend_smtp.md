# Resend SMTP (Mesencsi)

**Not MailerSend:** `smtp.mailersend.net` is a different provider. For Resend use `smtp.resend.com` and `SMTP_USER=resend`.

Mesencsi uses generic SMTP (`email_outbound.send_plain_email`). No Resend SDK required — only `.env` variables.

Official reference: [Resend — Send with SMTP](https://resend.com/docs/send-with-smtp)

## Credentials

| Variable | Value |
|----------|--------|
| `SMTP_HOST` | `smtp.resend.com` |
| `SMTP_PORT` | `587` (STARTTLS) or `465` (implicit SSL) |
| `SMTP_USE_TLS` | `1` for port 587; for port 465 TLS mode is implicit (see `email_outbound`) |
| `SMTP_USER` | `resend` (literal username, not your email) |
| `SMTP_PASSWORD` | Resend **API key** (`re_…`) from [API Keys](https://resend.com/api-keys) |
| `SMTP_FROM` | A **verified** sender in Resend (domain or single address) |

## Without your own domain yet (testing)

Resend allows a sandbox sender for quick tests:

- `SMTP_FROM=onboarding@resend.dev`
- Can only send to the **email address of your Resend account** (see Resend dashboard).

For real users (registration, password reset to arbitrary Gmail), add and verify your domain in Resend → Domains, then set e.g. `SMTP_FROM=noreply@yourdomain.hu`.

## Local `backend/.env` example

```env
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USE_TLS=1
SMTP_USER=resend
SMTP_PASSWORD=re_your_api_key_here
SMTP_FROM=onboarding@resend.dev
```

Restart uvicorn after changes.

Check (local only, no secrets in response):

```http
GET http://127.0.0.1:8000/dev/smtp-config
```

Expect: `"smtp_fully_configured": true`, `"smtp_mode": "relay"`.

## Render (staging / test)

Set the same keys in Render → Environment. Keep `FRONTEND_BASE_URL` / `PUBLIC_SITE_URL` on your `*.onrender.com` URL for staging.

`RENDER=true` requires full SMTP relay config at startup. Use `MESENCSI_PRODUCTION=false` on staging until Barion and final domain are ready.

## Apply script

From `backend/` (does not print your API key):

```powershell
$env:RESEND_API_KEY = "re_xxxxxxxx"
$env:RESEND_FROM = "onboarding@resend.dev"   # or noreply@yourdomain.hu
.\.venv\Scripts\python.exe scripts\apply_resend_smtp_env.py
```

Then restart uvicorn.

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| SMTP auth failed | Wrong API key, or `SMTP_USER` is not exactly `resend` |
| `send_ok` but no inbox | `SMTP_FROM` not verified; sandbox sender only delivers to account email |
| Links point to localhost | `FRONTEND_BASE_URL` still `127.0.0.1` on Render — set public URL |

Resend delivery logs: Resend dashboard → Emails.
