# Changelog — Mesencsi

All notable storefront/checkout changes. Customer-facing UI and emails are **Hungarian**; code and internal names may stay English.

## [Unreleased] — 2026-06-15

### Guest checkout

- Guests can browse the webshop, use the cart, and complete checkout **without login**.
- Login and registration remain available in the side rail; they are **not** shown inside checkout.
- Optional account creation CTA after successful guest payment (Barion return).
- Storybook reader and order history remain **account-only** (verified login required).

### Shipping

- **Active methods:** Személyes átvétel (0 Ft), GLS házhozszállítás (automatic tier price).
- **Foxpost:** intentionally **not active** — blocked server-side if submitted; not listed in `/shop/config`.
- Architecture remains provider-friendly: `shipping_method`, `shipping_price`, `shipping_metadata_json` on orders.

### GLS automatic pricing (backend source of truth)

| Shippable items | Package | Price |
|-----------------|---------|-------|
| 1–3 | Kis csomag | 2190 Ft |
| 4–6 | Közepes csomag | 2790 Ft |
| 7+ | Nagy csomag | 3290 Ft |

- Customer **cannot** manually select GLS package size.
- Frontend shows a preview only; `POST /orders/estimate` and order create recalculate on the server.
- Barion grand total includes shipping fee (`checkout_group_grand_total_huf`).

### Checkout UX

- Linear flow: cart lines → contact data → shipping method → address (GLS only) → optional shop message → order summary → submit.
- Single **„Rendelés elküldése”** button at the bottom.
- GLS address simplified: optional recipient name, zip/city, single street line, optional line2; Hungary assumed (not shown).
- No duplicate phone/email in shipping section; compact address confirmation checkbox before submit.

### Storybook editor (admin)

- Reader/preview text boxes: transparent background (no box chrome).
- Editor canvas: subtle outline on hover/focus only.

### Database

- `030` — guest checkout (`orders.user_id` nullable, guest idempotency).
- `031` — `shipping_method`, `shipping_price`, `shipping_metadata_json`.
- `032` — storybook page image layout fields.

### Docs

- Added [backend/docs/checkout_shipping_guest_qa.md](backend/docs/checkout_shipping_guest_qa.md) — manual QA checklist.
- Updated handover, review, and pre-production QA docs for guest checkout and shipping.
