# Local dev cleanup (safe ops notes)

This project uses a real Postgres database in local dev when `POSTGRES_*` env vars are set. Some manual QA/debug flows may create test users and other rows in that DB.

## Remove accidental debug users (Postgres)

If you created throwaway users during local QA (e.g. `debug_auth_regression_*`), you can delete them directly in Postgres.

**Warning**: deleting users can cascade/leave related rows depending on your DB constraints and app logic. Prefer doing this only on local/dev databases.

Example (psql):

```sql
BEGIN;

-- Inspect candidates first
SELECT id, username, email, created_at
FROM users
WHERE username LIKE 'debug_auth_regression_%'
   OR email LIKE 'debug_auth_regression_%';

-- Delete them (local/dev only)
DELETE FROM users
WHERE username LIKE 'debug_auth_regression_%'
   OR email LIKE 'debug_auth_regression_%';

COMMIT;
```

If you prefer soft-delete semantics, use an `UPDATE` instead of `DELETE` (set `is_deleted=true` and `deleted_at=now()`), but note some code paths treat deleted users differently.

## Local QA helper: known test user

If local login QA is blocked (no verified user / password reset email not configured), you can create/reset a known local shop user:

```bash
python backend/scripts/dev_seed_qa_shop_user.py
```

Credentials:

- **email**: `qa_user@example.com`
- **password**: `Test1234!`

This script is **local/dev only** and refuses to run when `MESENCSI_PRODUCTION=true` or on hosted deployments.

For end-to-end verification and password-reset QA (Mailpit, log links, checklist), see [local_auth_email_qa.md](local_auth_email_qa.md).

