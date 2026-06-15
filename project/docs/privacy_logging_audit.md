# MESENCSI privacy logging audit

Audit date: 2026-06-14

Scope: backend application logs, SMTP diagnostics, authentication, password reset, payment confirmation, Barion integration, incident persistence and frontend debug storage.

## Result

Production application logging is hardened against the developer-side NO-GO items identified in this sprint:

- raw recipient e-mail addresses in the main auth and SMTP paths are masked;
- passwords are not logged;
- SMTP password previews no longer expose any password characters;
- authentication, reset and verification tokens are not logged in production;
- Barion identifiers are truncated in operational logs where appropriate;
- request `Authorization` and `Cookie` header values are not logged by application code.

## Changes made

| Area | Previous risk | Change |
| --- | --- | --- |
| Registration logs | Raw registration e-mail was logged | Replaced with masked recipient identifier such as `e***@example.com` |
| SMTP send logs | Raw destination e-mail was logged | Replaced with masked recipient identifier |
| Hosted QA bootstrap | Raw QA account e-mail was logged | Replaced with masked recipient identifier |
| SMTP credential proof | First and last password characters were exposed by a preview helper | Preview now returns only length plus `[REDACTED]`; login logs only `password_configured` |
| Transactional e-mails | Debug/body handling was spread across templates | Common send path now appends the compliance footer; production send logs remain metadata-only |

## Token review

- User/admin JWTs are created and sent as cookies/API responses but are not emitted by production log statements.
- Password reset and e-mail verification links are logged only when `MESENCSI_PRODUCTION` is false.
- Barion IPN secrets and authorization headers are read for verification but are not logged.
- Payment IDs may appear only in truncated form in application events.

## Remaining risks

1. Local development deliberately logs verification and password-reset URLs when SMTP is unavailable. These URLs contain one-time tokens. The code blocks this behavior when `MESENCSI_PRODUCTION=true`, but development logs still require restricted access and short retention.
2. `logger.debug("[email] body preview...")` can contain personal data or one-time links in local no-SMTP mode. It is unreachable after the production SMTP-required guard, but developers should avoid enabling verbose debug logs on shared environments.
3. Incident records store exception messages and tracebacks. Framework/database exceptions can include query parameters. Access control and retention for the `incidents` table must be set operationally.
4. Reverse proxy, hosting platform, SMTP provider, Barion and APM logs are outside this source-code audit. Their request-body/header redaction and retention settings require deployment review.
5. `shop_qa_bootstrap.py` creates or updates a hosted QA user when QA credentials are configured. Production should not define `QA_SHOP_EMAIL` or `QA_SHOP_PASSWORD`.

## Recommendations

- Set `MESENCSI_PRODUCTION=true` in production and verify startup validation succeeds.
- Keep production log level at `INFO` or higher.
- Disable request-body logging at proxy/APM layers and redact `Authorization`, `Cookie`, password, token and address fields.
- Restrict incident/log access to named operators and define retention/deletion schedules.
- Do not configure hosted QA credentials in production.
- Periodically run source searches for `password`, `token`, `Authorization`, `Cookie`, `email=%s`, request payload logging and `console.log`.

## Evidence

- Full backend suite: `268 passed, 3 skipped`.
- Compliance browser suite: `3 passed`.
- Source audit covered `logger.*`, `_log.*`, `log_event`, cookie setters, local/session storage calls and auth/payment handlers.
