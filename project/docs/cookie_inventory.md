# MESENCSI cookie and browser storage inventory

Audit date: 2026-07-13

Consent policy version: `2026-07-13`

This is a technical inventory. Legal purpose, legal basis, retention wording and third-party disclosures must be approved by legal counsel before production publication.

## Cookies

| Name | Provider/domain | Purpose | Category | Lifetime | HttpOnly | Secure | SameSite | Created by | Consent gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `mesencsi_user_token` | MESENCSI, first party | Authenticated shop-user session | Necessary | Browser session | Yes | Yes on HTTPS | Lax | `backend/routers/user_auth.py` | Always available; required for account and checkout |
| `mesencsi_admin_token` | MESENCSI, first party | Authenticated admin session | Necessary | Browser session | Yes | Yes on HTTPS | Lax | `backend/routers/admin_auth.py` | Always available; admin-only |
| `mesencsi_csrf` | MESENCSI, first party | Double-submit CSRF protection | Necessary | Browser session | No, the frontend must read it | Yes on HTTPS | Lax | `backend/grafi_core/security/csrf.py` | Always available; security control |

No analytics or marketing cookie was found in the audited source.

## Local storage

| Key | Purpose | Category | Retention | Writer/reader | Consent behavior |
| --- | --- | --- | --- | --- | --- |
| `mesencsi_cookie_consent_v1` | Stores the versioned consent decision and timestamp | Necessary | Until removed or policy version changes | `frontend/js/cookie-consent.js` | Always allowed |
| `mesencsi_user_profile_json` | Cached display data for the logged-in shop user | Functional | Until logout, withdrawal, browser deletion or replacement | `frontend/js/auth-ui.js` | Blocked until functional consent; removed on withdrawal |
| `mesencsi_cart_v1` and `mesencsi_cart_*` | Local cart fallback/cache | Functional | Until cart replacement, withdrawal or browser deletion | `frontend/js/cart.js` | Blocked until functional consent; removed on withdrawal |
| `mesencsi_selected_coupon` | Last selected coupon | Functional | Until replacement, withdrawal or browser deletion | `frontend/js/cart.js` | Blocked until functional consent; removed on withdrawal |
| `admin_role` | Admin UI display state | Necessary for the separate admin UI | Until logout/browser deletion | `frontend/admin-login.html` | Not governed by the public storefront banner; admin-only |
| `admin_username` | Admin UI display state | Necessary for the separate admin UI | Until logout/browser deletion | `frontend/admin-login.html` | Not governed by the public storefront banner; admin-only |
| `debugStorybookV2` | Opt-in developer debug flag, read only by the app | Development-only | Until manually deleted | `frontend/storybook-reader-v2.js` | Treated as functional when accessed through the shared storage gate; direct debug read remains a development aid |
| `token` | Legacy read-only token key | Legacy | Existing browser value only; no current writer found | `frontend/js/boot.js` | Recommendation: remove the legacy read after a compatibility sunset |
| `mesencsi_user_access_token` | Legacy cleanup key | Legacy | Removed on logout; no current writer found | `frontend/js/auth-ui.js` | No JWT is currently written to local storage |

## Session storage

| Key | Purpose | Category | Retention | Writer/reader | Consent behavior |
| --- | --- | --- | --- | --- | --- |
| `mesencsi_guest_checkout_token` | Links and authorizes the guest checkout flow | Necessary | Current browser tab session or earlier programmatic removal | `frontend/js/checkout.js` | Always allowed; required for guest checkout |
| `mesencsi_guest_checkout_email` | Links the supplied guest e-mail address to the checkout/payment return flow | Necessary | Current browser tab session or earlier programmatic removal | `frontend/js/checkout.js` | Always allowed; required for guest checkout |
| `mesencsi_barion_checkout_redirect` | Marks an in-progress Barion redirect so return/abandonment UX can be handled | Necessary | Current browser tab session | `frontend/js/checkout.js` | Always allowed because it is required for the payment transition |

## Other storage observations

- Authentication JWTs are stored in `HttpOnly` cookies, not local storage.
- The CSRF token is intentionally readable by frontend JavaScript and must match the `X-CSRF-Token` header.
- Cookie `Secure` is enabled when the request scheme is HTTPS. Production must terminate or correctly forward HTTPS.
- No explicit `Max-Age` or `Expires` is set on the audited cookies; they are browser-session cookies.
- No third-party browser script or third-party cookie writer was found in the storefront source.

## Withdrawal behavior

The footer link `Süti beállítások` reopens preferences. Selecting withdrawal stores a necessary-only decision and removes known functional keys and `mesencsi_cart_*` keys. It does not remove authentication or CSRF cookies because those are necessary and are managed through logout/session expiry.

## Review notes

- The public policy describes the categories, legal bases, retention behavior and the policy-version change rule reflected by the audited implementation.
- Admin-only local storage is identified separately from the public storefront consent choice.
- Barion browser storage occurs on Barion-controlled pages and remains outside this repository audit.
