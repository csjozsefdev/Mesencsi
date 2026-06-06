# SMTP — Gmail locally, same variables on Render

Registration and order emails use **`send_plain_email`** in `email_outbound.py`. Configuration is read from environment variables (loaded from `backend/.env` locally).

## Modes

| Mode | When | `smtp_fully_configured` | Docker |
|------|------|---------------------------|--------|
| **relay** | `SMTP_HOST` + `SMTP_USER` + `SMTP_PASSWORD` + `SMTP_FROM` | `true` | Not required |
| **mailpit** | Local only: `127.0.0.1:1025`, `SMTP_USE_TLS=0` | `false` | Optional (`docker compose up -d mailpit`) |
| **none** | No `SMTP_HOST` | `false` | — |

Hosted (Render / staging / `MESENCSI_PRODUCTION`) **requires relay mode** — startup fails if not fully configured.

## Resend (local + Render)

See **[resend_smtp.md](resend_smtp.md)**. Quick reference:

```env
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USE_TLS=1
SMTP_USER=resend
SMTP_PASSWORD=re_your_api_key
SMTP_FROM=onboarding@resend.dev
```

`SMTP_USER` is always the literal string `resend`. Password is the API key (`re_…`).

## Gmail (local + Render)

Use a [Google App Password](https://support.google.com/accounts/answer/185833) (2-Step Verification required). Put values in **`backend/.env`** locally; copy the **same keys** to Render → Environment.

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=1
SMTP_USER=your.address@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
SMTP_FROM=your.address@gmail.com
```

After editing `.env`, **restart uvicorn** (env is loaded at process start).

Check locally (no secrets in response):

```http
GET http://127.0.0.1:8000/dev/smtp-config
```

Expect: `"smtp_fully_configured": true`, `"smtp_mode": "relay"`, `"smtp_transport_mode": "starttls"`.

## Optional Mailpit (local only)

```env
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
SMTP_USE_TLS=0
SMTP_FROM=noreply@localhost
```

UI: `http://127.0.0.1:8025`. Do not use Mailpit on Render — use relay SMTP instead.

## Render dashboard

| Variable | Gmail example |
|----------|----------------|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USE_TLS` | `1` |
| `SMTP_USER` | your Gmail address |
| `SMTP_PASSWORD` | App Password (secret) |
| `SMTP_FROM` | same as `SMTP_USER` |

Also set `FRONTEND_BASE_URL` / `PUBLIC_SITE_URL` / `BACKEND_PUBLIC_URL` to your public HTTPS URLs.

`RENDER=true` is set automatically on Render.com and enforces full SMTP at startup.

## Troubleshooting

1. **Partial config** (`smtp_mode: partial`) — Gmail needs all four fields; Mailpit needs host + port 1025 + `SMTP_USE_TLS=0` + `SMTP_FROM`.
2. **Restart** the server after changing `.env`.
3. Logs show `error_type=` on failure; passwords are never logged.
4. Gmail blocks: use App Password, not your normal account password.

See also: [deploy_readiness.md](./deploy_readiness.md).
