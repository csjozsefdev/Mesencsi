# Mesencsi — Barion sandbox tesztelési terv

**Csak sandbox.** Ne használj éles Bariont (`BARION_ENV=production`, `api.barion.com`, `secure.barion.com`) ezen a checklisten.

A backend a `BARION_ENV` alapján választ API-t és gateway-t (`barion_api.py`). Sandbox alapértelmezés:

| Komponens | Sandbox érték |
|-----------|----------------|
| Env | `BARION_ENV=sandbox` |
| REST API | `https://api.test.barion.com` → `POST /v2/Payment/Start`, `GET /v2/Payment/GetPaymentState` |
| Böngészős fizetés | `https://secure.test.barion.com/Pay?id={PaymentId}` |
| POSKey | `BARION_POS_KEY` a `.env`-ből (Barion **teszt** fiók) |
| RedirectUrl | `BARION_RETURN_URL` vagy automatikus: `{BARION_BACKEND_PUBLIC_URL}/payments/barion/return` |
| CallbackUrl (IPN) | `BARION_CALLBACK_URL` vagy automatikus: `{BARION_BACKEND_PUBLIC_URL}/payments/barion/ipn` (+ opcionális `barion_ipn` query) |

---

## 1. Szükséges env változók (backend `.env`)

```env
# Kötelező sandbox teszthez (valós Barion API, nem stub)
BARION_ENV=sandbox
BARION_POS_KEY=<sandbox POSKey a Barion teszt felületről>
BARION_PAYEE_EMAIL=<a Barion shop regisztrált payee e-mailje>

# Publikus URL-ek — lokálisan gyakran ngrok / tunnel kell IPN-hez
BARION_BACKEND_PUBLIC_URL=https://<publikus-host>
BARION_FRONTEND_LANDING_URL=https://<publikus-host>
PUBLIC_SITE_URL=https://<publikus-host>

# Opcionális felülírás (alapból sandbox hostok jönnek BARION_ENV-ből):
# BARION_API_BASE_URL=https://api.test.barion.com
# BARION_GATEWAY_URL=https://secure.test.barion.com/Pay

# Return / Callback explicit (ha nem az automatikus építést használod):
# BARION_RETURN_URL=https://<publikus-host>/payments/barion/return
# BARION_CALLBACK_URL=https://<publikus-host>/payments/barion/ipn
BARION_IPN_SECRET=<erős random titok — ajánlott sandboxban is>

# Shop JWT + admin (checkout / admin lista)
USER_JWT_SECRET=...
ADMIN_JWT_SECRET=...

# SMTP (fizetés visszaigazoló levél — külön manuális ellenőrzés)
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
SMTP_USE_TLS=0
```

| Változó | Szerep |
|---------|--------|
| `BARION_ENV=sandbox` | **Kötelező** — `api.test.barion.com` + `secure.test.barion.com` |
| `BARION_POS_KEY` | Payment/Start + GetPaymentState (`x-pos-key` / body POSKey) |
| `BARION_PAYEE_EMAIL` | Tranzakció Payee mező |
| `BARION_BACKEND_PUBLIC_URL` | Return + IPN URL alapja |
| `BARION_RETURN_URL` | Barion `RedirectUrl` (üres → `/payments/barion/return`) |
| `BARION_CALLBACK_URL` | Barion `CallbackUrl` / IPN (üres → `/payments/barion/ipn`) |
| `BARION_IPN_SECRET` | IPN auth; Payment/Start automatikusan `?barion_ipn=…` a CallbackUrl-en |
| `BARION_FRONTEND_LANDING_URL` | Return után bolt: `/?payment=barion&result=…` |
| `MESENCSI_PRODUCTION` | **Ne** legyen `true` sandbox tesztnél (stub tiltás) |

**Stub mód (NEM ez a dokumentum célja):** üres `BARION_POS_KEY` → `preview-…` id, nincs valós Barion API. Sandbox teszthez **kötelező** a POSKey.

---

## 2. Sandbox account / POSKey hol van?

1. Barion **teszt / sandbox** merchant felület (Barion dokumentáció: [Payment Start v2](https://docs.barion.com/Payment-Start-v2), [Callback mechanism](https://docs.barion.com/Callback_mechanism)).
2. A shop **POSKey** (teszt kulcs) — másolás a backend `.env` → `BARION_POS_KEY`.
3. **Payee e-mail** — a Barion shop tulajdonos e-mailje → `BARION_PAYEE_EMAIL`.

A kulcsot **ne** commitold; csak `.env` / titoktár.

---

## 3. Backend indítás és sandbox ellenőrzés

```powershell
cd backend
copy .env.example .env
# Töltsd ki: BARION_ENV=sandbox, BARION_POS_KEY, BARION_PAYEE_EMAIL, URL-ek, JWT, SMTP

.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn mesencsi:app --host 127.0.0.1 --port 8000
```

**Gyors config check (titok nélkül):**

```http
GET http://127.0.0.1:8000/payments/barion/status
```

Elvárt (sandbox REST):

```json
{
  "sandbox": true,
  "barion_env": "sandbox",
  "pos_key_configured": true,
  "rest_api_enabled": true,
  "barion_ipn_secret_configured": true
}
```

Ha `rest_api_enabled: false` → nincs `BARION_POS_KEY`.

### Lokális IPN / Return

A Barion a **publikus HTTPS** `RedirectUrl` / `CallbackUrl` felé hív. Csak `127.0.0.1` mellett:

- **Return:** a böngészőről gyakran elég (a vásárló visszajön).
- **IPN:** Barion szerverről jön — tunnel kell (pl. ngrok, Cloudflare Tunnel) → `BARION_BACKEND_PUBLIC_URL` = tunnel URL.

Callback automatikus építés: `attach_barion_ipn_query()` hozzáadja a `barion_ipn` query-t, ha van `BARION_IPN_SECRET`.

---

## 4. Teszt flow — lépésről lépésre

A rendelés **fizetési** állapota: `orders.payment_status` (`pending` | `paid` | `failed` | `cancelled`).  
Az üzleti állapot: `orders.status` (pl. `new` → admin `completed`).

| # | Lépés | Implementáció | Ellenőrzés |
|---|--------|----------------|------------|
| 1 | Rendelés pending fizetéssel | `POST /orders` (verified user) → `payment_status=pending`, `status=new` | DB / `GET /orders` |
| 2 | Payment/Start | `POST /payments/barion/start` `{ "order_ids": [...] }` | Log: `barion_payment_start` |
| 3 | PaymentId mentés | `orders.barion_payment_id` = Barion `PaymentId` | DB minden checkout soron |
| 4 | Redirect sandbox Pay | Válasz `redirect_url` → `https://secure.test.barion.com/Pay?id=…` | Böngésző Barion teszt UI |
| 5 | IPN fogadás | Barion POST → `POST /payments/barion/ipn` | Log: `barion_orders_synced` vagy `barion_ipn_sync_failed` + JSON `sync` |
| 6 | GetPaymentState verify | IPN **és** return **és** logged-in poll: `sync_orders_payment_status_from_barion` | Egyetlen `paid` forrás REST módban |
| 7 | Csak siker → paid | Barion `Succeeded` → `payment_status=paid` | **Nem** csak frontend redirect |
| 8 | failed/cancelled/expired | Barion `Failed` / `Canceled` / `Expired` → `failed` / `cancelled` / `pending` | **Nem** `paid`, nincs visszaigazoló levél |
| 9 | Admin lista | `GET /admin/orders` | `payment_status` oszlop; `completed` csak `paid` mellett |

### API útvonalak (összefoglaló)

| Művelet | Endpoint |
|---------|----------|
| Rendelés | `POST /orders` |
| Fizetés indítás | `POST /payments/barion/start` |
| Vásárló visszatér | `GET /payments/barion/return?paymentId=…` |
| IPN | `POST /payments/barion/ipn` |
| Állapot (bejelentkezve) | `GET /payments/barion/payment/{payment_id}/state` |
| Config | `GET /payments/barion/status` |

### Barion → shop állapot map

| Barion `Status` | `orders.payment_status` |
|-----------------|-------------------------|
| `Succeeded`, `PartiallySucceeded` | `paid` |
| `Canceled`, `Cancelled` | `cancelled` |
| `Failed`, `Expired`, `Rejected` | `failed` |
| Egyéb / folyamatban | `pending` |

**Admin:** `payment_status=paid` **nem** állítható kézzel. `status=completed` csak ha `payment_status=paid` (különben 409).

---

## 5. Teszt rendelés indítás (storefront)

**Előfeltétel:** legalább 1 aktív termék. Vendég **vagy** verified shop user.

### Vendég

1. Nyisd meg: `http://127.0.0.1:8000/` (belépés nélkül)
2. Webshop → kosárba termék → **Kosár**
3. Kapcsolati adatok + szállítási mód (+ GLS cím ha kell) → **Rendelés elküldése**
4. Barion sandbox fizetés

### Belépett vásárló

1. Belépés → webshop → kosár
2. Ugyanaz a checkout folyamat (tagi kupon opcionális)

Mindkét esetben:

- Backend: `POST /orders` → 201, sorok `payment_status=pending`
- Frontend: `POST /payments/barion/start` → `redirect_url` → Barion teszt oldal
- A Barion összeg tartalmazza a szállítási díjat (GLS: 2190 / 2790 / 3290 Ft csomagméret szerint)

**Második start ugyanarra a pending csoportra:** `resumed_existing: true`, ugyanaz a `payment_id` (nem új Payment/Start).

---

## 6. Sikeres fizetés ellenőrzése

### Barion sandboxon

- Teszt kártya / wallet a Barion teszt dokumentáció szerint
- Fizetés **Succeeded**

### Visszatérés után

1. Böngésző: `{FRONTEND}/?payment=barion&result=paid&pid=…`
2. Storefront banner / rendelések: fizetve
3. **DB:**

```sql
SELECT id, payment_status, status, barion_payment_id
FROM orders
WHERE barion_payment_id = '<PaymentId>';
-- payment_status = 'paid', status általában 'new'
```

4. **Szerver log:**
   - `barion_orders_synced` … `shop_status=paid`
   - `payment_confirmation_email_sent` (ha SMTP OK)

5. **Dupla return / IPN:** továbbra is `paid`, **egy** visszaigazoló e-mail

6. **Nincs** manuális `paid` beállítás adminból

---

## 7. Sikertelen / megszakított fizetés ellenőrzése

| Forgatókönyv | Barion oldalon | Elvárt `payment_status` | Levél |
|--------------|----------------|-------------------------|-------|
| Elutasított kártya | Failed | `failed` | Nincs |
| Felhasználó mégse | Canceled | `cancelled` | Nincs |
| Timeout / Expired | Expired | `failed` | Nincs |
| Return sync hiba | — | marad `pending` (vagy előző) | Nincs |

Ellenőrzés:

1. Return URL: `result=failed` vagy `result=cancelled` (nem `paid`)
2. DB: **nem** `paid`
3. `GET /orders` (user): pending / failed / cancelled látszik
4. Admin: **Teljesítve** (`completed`) **nem** állítható, amíg `payment_status != paid`

Opcionális: `GET /payments/barion/cancel?paymentId=…` — szintén GetPaymentState sync (nem feltételezi a cancelled-et).

---

## 8. Admin státusz ellenőrzés

1. `http://127.0.0.1:8000/admin/login` → owner JWT
2. **Rendelések** menü
3. Teszt rendelés sorai:
   - Fizetés előtt: `payment_status` = **Függő** / pending
   - Sikeres Barion után: **Fizetve** / paid
   - Sikertelen után: failed / cancelled — **nem** fizetve
4. Állapot módosítás:
   - `completed` **csak** paid mellett → OK
   - `completed` pending mellett → **409** „Csak fizetett rendelés teljesíthető.”
5. Fizetési állapot: admin **nem** állíthat `paid`-re (400)

---

## 9. Mit nem automatizálunk E2E-ben

A Playwright E2E (`e2e/`, lásd `E2E_TESTING.md`) **szándékosan nem**:

| Terület | Ok |
|---------|-----|
| Valódi Barion `secure.test.barion.com` fizetés | Külső UI, teszt kártya, iframe |
| Teljes `POST /orders` + `POST /payments/barion/start` + redirect | Barion domain |
| IPN Barion szerverről | Publikus URL / tunnel |
| SMTP inbox / Mailpit tartalom | E-mail QA külön |
| Admin `completed` workflow minden kombináció | Manuális admin checklist |
| `paid` visszaállítás SMTP hiba esetén | Üzleti szabály: paid marad |

E2E **csak:** stub query `/?payment=barion&pid=preview-…` — storefront nem omlik össze.

**Automatizált backend (pytest):** Barion HTTP mock, IPN auth, duplicate start guard, GetPaymentState map, email csak `paid` + `rows_updated` esetén.

---

## 10. Gyors checklist (sandbox sign-off)

- [ ] `GET /payments/barion/status` → `sandbox: true`, `rest_api_enabled: true`
- [ ] API host: `api.test.barion.com` (log / hálózat)
- [ ] Redirect: `secure.test.barion.com/Pay`
- [ ] Rendelés → `payment_status=pending`, `barion_payment_id` üres majd töltődik
- [ ] Sikeres fizetés → `paid`, max. 1 levél
- [ ] Sikertelen → nem `paid`, nincs levél
- [ ] IPN + return után konzisztens DB
- [ ] Admin lista + `completed` guard
- [ ] **Nincs** éles `BARION_ENV=production` a teszt `.env`-ben

---

## Kapcsolódó dokumentumok

- [backend/docs/deploy_readiness.md](backend/docs/deploy_readiness.md) — deploy + Barion összefoglaló
- [E2E_TESTING.md](E2E_TESTING.md) — Gate rend (manuális Barion = 4. lépés)
- [backend/docs/gate_commands.md](backend/docs/gate_commands.md)
