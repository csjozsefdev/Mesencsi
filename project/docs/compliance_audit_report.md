# MESENCSI final compliance audit report

Audit date: 2026-06-14

Verdict: **CONDITIONAL GO**

The developer-side compliance controls requested for this sprint are implemented and automated tests pass. Production launch remains conditional on lawyer-approved final legal content, production PostgreSQL migration/smoke evidence and deployment configuration validation.

## Compliance status

| Area | Status | Evidence |
| --- | --- | --- |
| Cookie compliance | PASS | First-visit banner, accept-all, necessary-only, settings, versioned local decision, footer reopening, change and withdrawal. Functional local storage is blocked before consent and cleared on withdrawal. Playwright compliance test passed. |
| Registration compliance | PASS | Two required frontend controls; backend rejects missing/false acknowledgements; server stores timestamps and separate terms/privacy versions. Positive and negative API tests passed. |
| Checkout compliance | PASS | Existing address confirmation preserved; two required legal controls added; backend validation and order evidence storage implemented; legal links and payment-obligation button present. |
| Legal page wiring | PASS (framework) | `/aszf`, `/adatkezeles`, `/impresszum`, `/elallas`, `/szallitas`, `/fizetes`, `/panaszkezeles`, `/sutik` serve and render. Missing pages contain structured legal TODO placeholders and last-updated/version sections. |
| Email compliance | PASS | Common transactional send path appends Mesencsi, Impresszum and Adatkezelés links generated from `PUBLIC_SITE_URL`. Production requires HTTPS `PUBLIC_SITE_URL`. |
| Barion disclosure | PASS | Checkout and `/fizetes` state that the payment process is handled by Barion; payment flow code was not changed. |
| Privacy logging | PASS with documented residual risk | Raw primary-path recipient logs masked; password preview removed; production token logging not found. Dev token-link and infrastructure-log risks are documented separately. |
| Migration | PASS for revision 025; production execution pending | Alembic has one head (`025`). Isolated `024 -> 025` execution added all four columns to both tables. Full historical SQLite migration is not supported because revision 003 uses PostgreSQL `now()`; production PostgreSQL execution remains a launch gate. |

## Database evidence

Migration: `backend/alembic/versions/025_compliance_acceptances.py`

Users:

- `terms_accepted_at`
- `terms_version`
- `privacy_acknowledged_at`
- `privacy_version`

Orders:

- `terms_accepted_at`
- `terms_version`
- `privacy_acknowledged_at`
- `privacy_version`

Legacy rows remain nullable. The migration does not fabricate historical acceptance.

## QA evidence

### Backend

Command:

```text
backend\.venv\Scripts\python.exe -m pytest -q
```

Result:

```text
268 passed, 3 skipped, 1 deprecation warning
```

The skipped tests are environment-dependent PostgreSQL/media checks already marked by the existing suite.

### Browser

Command:

```text
npm.cmd test -- --project=public compliance.public.spec.ts
```

Result:

```text
3 passed
```

Covered:

- consent before functional storage;
- necessary-only decision;
- version and timestamp storage;
- footer reopening;
- enabling functional storage;
- withdrawal and optional-key deletion;
- all eight legal routes;
- registration and checkout controls;
- Barion disclosure and payment-obligation button.

### Migration

- `alembic heads` returned `025 (head)`.
- Isolated `024 -> 025` upgrade succeeded.
- Resulting `users` and `orders` tables contained all four compliance columns.

### Static checks

- Modified JavaScript files passed `node --check`.
- `git diff --check` passed.

## Modified files

Backend:

- `backend/alembic/versions/025_compliance_acceptances.py`
- `backend/db_models.py`
- `backend/email_outbound.py`
- `backend/mesencsi.py`
- `backend/models.py`
- `backend/policy_versions.py`
- `backend/routers/user_auth.py`
- `backend/shop_qa_bootstrap.py`
- `backend/smtp_credential_proof.py`
- `backend/startup_config.py`

Frontend:

- `frontend/js/auth-ui.js`
- `frontend/js/checkout.js`
- `frontend/js/cookie-consent.js`
- `frontend/js/router.js`
- `frontend/js/storage.js`
- `frontend/mesencsi.html`
- `frontend/style.css`

Tests and QA:

- `backend/tests/test_auth_email_verify_flow.py`
- `backend/tests/test_cart_persistence.py`
- `backend/tests/test_checkout_bundle_integration.py`
- `backend/tests/test_compliance_acceptances.py`
- `backend/tests/test_csrf_cookie_flow.py`
- `backend/tests/test_email_outbound.py`
- `backend/tests/test_shipping_address_validation.py`
- `backend/tests/test_startup_config.py`
- `e2e/global-setup.ts`
- `e2e/helpers/auth-api.ts`
- `e2e/tests/compliance.public.spec.ts`

Documentation:

- `docs/cookie_inventory.md`
- `docs/privacy_logging_audit.md`
- `docs/compliance_audit_report.md`

## Legal-counsel dependencies

- Replace every legal TODO/placeholder with approved final content.
- Review the pre-existing ÁSZF, privacy and impressum text and confirm all business/entity details.
- Approve the withdrawal form, exceptions, complaint handling, delivery/payment terms and consumer-information wording.
- Approve cookie purposes, categories, legal bases and retention periods.
- Confirm Barion service-provider and data-transfer wording.
- Assign final policy versions and update `policy_versions.py` and cookie consent version when approved content changes.

## Production launch gates

Before changing this verdict to GO:

1. Legal counsel signs off all eight legal pages and no TODO remains.
2. Run `alembic upgrade head` against a production-like PostgreSQL backup/clone, then verify acceptance columns and rollback/recovery procedure.
3. Run production startup validation with HTTPS `PUBLIC_SITE_URL`, real PostgreSQL, SMTP, CORS and Barion settings.
4. Perform a production-domain smoke test for cookies, registration, checkout, legal links, e-mail links and Barion redirect/return.
5. Confirm proxy/APM/provider log redaction and retention.

Until all five gates are evidenced, the release is **CONDITIONAL GO**, not final GO.
