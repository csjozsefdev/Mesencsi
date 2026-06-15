# Checkout, shipping & guest order — QA checklist

Use after changes to cart, checkout, shipping, Barion, or guest flows.  
Automated gate: `cd backend && python -m pytest -q` (~344 passed, 3 skipped).

**Language:** customer UI and emails — Hungarian. Code/tests — English.

---

## Guest & public access

- [ ] Logged-out user can open **Webshop** and see products.
- [ ] Logged-out user can **add to cart** and open **Kosár**.
- [ ] Checkout form shows **Kapcsolati adatok** (name, email, phone) — no Belépés/Regisztráció block inside checkout.
- [ ] Guest can submit order and reach **Barion** sandbox.
- [ ] After successful guest payment, optional **„Fiók létrehozása”** offer appears (can dismiss).
- [ ] **Storybook reader** still requires login (guest cannot read purchased books without account).
- [ ] **Fiók → Rendeléseim** still requires login.

## Logged-in checkout

- [ ] Verified user checkout works; email field readonly from profile.
- [ ] Member coupon / combo discounts apply via estimate API.
- [ ] Profile address import fills GLS fields (optional recipient, zip, city, street line).

## Shipping methods

- [ ] **Személyes átvétel** — shipping fee **0 Ft** in summary and order.
- [ ] Personal pickup **hides** address fields and confirmation checkbox.
- [ ] **GLS házhozszállítás** — dropdown only (no manual package-size selector).

## GLS automatic tiers (hard refresh: Ctrl+F5)

| Cart qty (shippable) | Expected package | Expected fee |
|----------------------|------------------|--------------|
| 1–3 | Kis csomag | **2190 Ft** |
| 4–6 | Közepes csomag | **2790 Ft** |
| 7+ | Nagy csomag | **3290 Ft** |

- [ ] UI shows **„Számított GLS díj: …”** under shipping method.
- [ ] Order summary at **bottom** shows shipping method, package label (GLS), fee, **Végösszeg** once.
- [ ] Changing cart quantity updates tier/fee after estimate refresh.

## GLS address (simplified)

- [ ] Section title: **„Szállítási cím”**.
- [ ] **Átvevő neve** optional — empty uses customer name on order.
- [ ] Different recipient name stored when filled.
- [ ] **Irányítószám**, **Város**, **Utca, házszám** required for GLS.
- [ ] No separate **Ország** field (stored as Magyarország).
- [ ] No phone/email duplicated in shipping block.
- [ ] Checkbox: **„Megnéztem, a szállítási adatok helyesek.”** above submit (GLS only).

## Barion & totals

- [ ] `POST /orders/estimate` shipping price matches order create.
- [ ] Barion charged amount = products total + shipping (check sandbox receipt / DB `shipping_price`).
- [ ] Failed/cancelled payment does not mark order paid.

## Email & admin

- [ ] Payment confirmation email: shipping method, fee, and **Szállítási cím** block (GLS).
- [ ] Admin order detail: guest vs registered customer, shipping method, fee, GLS package label, delivery address.
- [ ] Foxpost method **not** offered in shop config; manual submit returns 422.

## Storybook (smoke)

- [ ] Admin storybook editor: text boxes visible on hover/focus; reader preview without grey boxes.

## Regression

- [ ] Unverified **logged-in** user still cannot place order (403).
- [ ] Idempotency-Key prevents duplicate order groups.
- [ ] Mobile layout: checkout fields stack readably.

---

## Sign-off

| Tester | Date | Environment | Pass/Fail |
|--------|------|-------------|-----------|
| | | local / staging | |
