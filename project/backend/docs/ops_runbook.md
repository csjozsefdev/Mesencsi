# Mesencsi ops runbook (minimum viable)

## Metrics
- Endpoint: `GET /internal/metrics`
- Auth: header `X-Metrics-Token: <METRICS_READ_TOKEN>`
- Notes: buckets paths to avoid high-cardinality IDs.

## Incidents (unhandled exceptions)
- Endpoint: `GET /internal/incidents?limit=50`
- Auth: header `X-Incidents-Token: <INCIDENTS_READ_TOKEN>`

## Payments (Barion)
- **Source of truth**: Barion `GetPaymentState` sync.
- **Recovery**:
  - Check order `barion_payment_id` + `payment_status` in DB.
  - Re-run sync via `GET /payments/barion/payment/{pid}/state` (shop user must be logged in).
  - If IPN storms happen, verify Barion credentials + callback URL + IPN secret.

## Uploads
- If `MEDIA_STORAGE=s3`: verify `S3_BUCKET`, credentials, `MEDIA_PUBLIC_BASE_URL`.
- Validate delete cleanup via storybook deletes (cover/page image/audio).

