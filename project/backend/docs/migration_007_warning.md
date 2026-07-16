# Migration 007 — data loss warning

Revision `007_orders_user_id_email_required` performs **destructive cleanup** on legacy checkout data:

- `DELETE FROM orders` — **all existing order rows are removed** before `user_id` is made NOT NULL.
- Empty `users.email` values are backfilled to `username@legacy.mesencsi.invalid`.

## When this matters

- **New production database:** run the full chain `alembic upgrade head` — no legacy orders exist.
- **Existing database already at revision ≥ 007:** safe to apply newer migrations only.
- **Legacy database stuck before 007 with real order data:** **do not** run `upgrade head` blindly. Back up first and plan a manual migration.

## Pre-deploy check

```bash
python scripts/predeploy_alembic_check.py
```

The script prints current/head revisions and exits with code `2` if it detects orders data on a DB still before 007.

## Rollback policy

Alembic downgrade is **not** the production rollback strategy for Mesencsi. Restore from PostgreSQL backup instead.
