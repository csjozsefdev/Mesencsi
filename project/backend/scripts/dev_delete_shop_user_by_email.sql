-- =============================================================================
-- LOCAL DEV ONLY — delete one shop user (users table) by email for SMTP retest
-- =============================================================================
-- Admin / maintenance logins are NOT in this database (OWNER_* / MAINTENANCE_* env).
-- Email verification tokens are columns on users (no separate token table):
--   email_verification_token, email_verification_sent_at, email_verified_at
--
-- Run against your LOCAL Postgres only (e.g. docker compose db on localhost).
-- Review the PREVIEW queries first, then run the DELETE block in a transaction.
--
-- Usage (from host, adjust password):
--   psql -h localhost -U mesencsi -d mesencsi -f scripts/dev_delete_shop_user_by_email.sql
--
-- Or paste into pgAdmin / DBeaver connected to local mesencsi DB.
-- =============================================================================

\set target_email 'csjozsefdev@gmail.com'

-- -----------------------------------------------------------------------------
-- STEP 0 — PREVIEW (read-only): confirm exactly one shop user and what will go
-- -----------------------------------------------------------------------------
SELECT id, username, email, email_verified_at,
       email_verification_token IS NOT NULL AS has_verify_token,
       is_active, is_deleted, created_at
FROM users
WHERE lower(email) = lower(:'target_email');

SELECT COUNT(*) AS order_rows
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE lower(u.email) = lower(:'target_email');

SELECT COUNT(*) AS cart_rows
FROM user_cart_items c
JOIN users u ON u.id = c.user_id
WHERE lower(u.email) = lower(:'target_email');

SELECT COUNT(*) AS coupon_rows_linked
FROM coupons c
JOIN users u ON u.id = c.user_id
WHERE lower(u.email) = lower(:'target_email');

SELECT COUNT(*) AS news_comment_rows
FROM news_comments nc
JOIN users u ON u.id = nc.user_id
WHERE lower(u.email) = lower(:'target_email');

SELECT *
FROM login_throttle
WHERE lower(email_normalized) = lower(:'target_email');

-- -----------------------------------------------------------------------------
-- STEP 1 — DELETE (safe order for FK constraints)
-- -----------------------------------------------------------------------------
BEGIN;

-- 1a) Barion payment attempts tied to this user's checkout groups (if any orders exist)
DELETE FROM payment_attempts pa
WHERE pa.checkout_group_id IN (
    SELECT DISTINCT o.checkout_group_id
    FROM orders o
    JOIN users u ON u.id = o.user_id
    WHERE lower(u.email) = lower(:'target_email')
      AND o.checkout_group_id IS NOT NULL
);

-- 1b) Shop orders (orders.user_id → users.id, NO ON DELETE CASCADE)
DELETE FROM orders o
USING users u
WHERE o.user_id = u.id
  AND lower(u.email) = lower(:'target_email');

-- 1c) Login throttle row for this email (separate table, not FK-linked)
DELETE FROM login_throttle
WHERE lower(email_normalized) = lower(:'target_email');

-- 1d) Shop user (removes verification token columns with the row;
--     user_cart_items CASCADE; coupons/news_comments user_id → NULL)
DELETE FROM users
WHERE lower(email) = lower(:'target_email');

-- Confirm gone
SELECT COUNT(*) AS users_remaining
FROM users
WHERE lower(email) = lower(:'target_email');

COMMIT;
