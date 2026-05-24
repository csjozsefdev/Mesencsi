# Manual QA — cart persistence & combo editor fixes

## Cart (shop user)

1. Log in, add 2 products to cart, open cart view — items visible.
2. Refresh page (F5) — cart still there.
3. Log out, log back in with same account — cart still there.
4. Log out, log in as a **different** user — cart should be empty or that user's own cart.
5. Complete checkout (or clear cart after paid Barion return) — cart empties on server and UI.

## Combo (admin owner)

1. Admin → Kombó kedvezmények → Új kombó szabály.
2. Check exactly two products (checkboxes, no Ctrl needed).
3. Save — success toast, rule appears in list with both product IDs.
4. Edit rule — previously selected products remain checked.

## Migration

Run once on dev DB: `alembic upgrade head` (included in `run.bat`).
