# Mesencsi ops runbook

Minimum operational guide for production. See also [deploy_readiness.md](./deploy_readiness.md).

---

## Deploy / migrations

1. `python scripts/predeploy_alembic_check.py` — legacy DB safety (exit `2` = stop)
2. `alembic upgrade head` — current head: **`032`**
3. Start app with `MESENCSI_PRODUCTION=true` and full env
4. Verify `GET /health` → 200

**Rollback:** restore PostgreSQL backup — do not rely on Alembic downgrade in production.

**007 warning:** [migration_007_warning.md](./migration_007_warning.md)

---

## Metrics

- Endpoint: `GET /internal/metrics`
- Auth: header `X-Metrics-Token: <METRICS_READ_TOKEN>`
- Notes: buckets paths to avoid high-cardinality IDs.

## Incidents (unhandled exceptions)

- Endpoint: `GET /internal/incidents?limit=50`
- Auth: header `X-Incidents-Token: <INCIDENTS_READ_TOKEN>`

---

## Email outbox

Payment confirmation emails are queued in `email_outbox` (not sent inline).

**Cron / scheduled job (recommended every 1–5 min):**

```bash
cd backend
python scripts/process_email_outbox.py 50
```

| Exit code | Meaning |
|-----------|---------|
| 0 | OK (nothing pending, or all sent) |
| 1 | Retriable failures remain (backoff) |
| 2 | Dead-letter rows created |
| 3 | Unexpected exception |

**Dead letters:** inspect `email_outbox` where `status = 'dead'`, fix SMTP/root cause, then:

```bash
python scripts/process_email_outbox.py --requeue-dead
```

Worker features: atomic claim (`FOR UPDATE SKIP LOCKED` on PostgreSQL), exponential backoff, `next_retry_at` (migration `029`).

---

## Payments (Barion)

- **Source of truth:** Barion `GetPaymentState` sync.
- **Checkout group:** `POST /payments/barion/start` requires the full order group — partial groups return 409.
- **Recovery:**
  - Check order `barion_payment_id` + `payment_status` in DB.
  - Re-run sync via `GET /payments/barion/payment/{pid}/state` (shop user must be logged in).
  - If IPN storms happen, verify Barion credentials + callback URL + IPN secret.

---

## Auth / sessions

- Shop JWT includes `token_version` (`tv`). Bumping `users.token_version` invalidates all existing tokens (password reset, ban, admin verify flow).
- Emails stored lowercase; login is case-insensitive.

---

## Order idempotency

- Clients may send `Idempotency-Key` on `POST /orders` (8–128 chars).
- Same key + same cart payload → returns existing orders.
- Same key + different payload → 409.

---

## Uploads

- If `MEDIA_STORAGE=s3`: verify `S3_BUCKET`, credentials, `MEDIA_PUBLIC_BASE_URL`.
- Local/default: `backend/media/uploads/` — ephemeral on Render without persistent disk.
- Validate delete cleanup via storybook deletes (cover/page image/audio).

---

## Rate limiting

- Single process: in-memory (`auth_limits.py`).
- Multiple workers/instances: set `REDIS_URL`.
