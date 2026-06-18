# Mesencsi — deploy readiness (praktikus checklist)

Utolsó séma: **Alembic `033_compliance_acceptances`** (`alembic upgrade head`).  
**007 figyelmeztetés:** lásd [migration_007_warning.md](./migration_007_warning.md) — a 007 migráció törli a meglévő `orders` sorokat.  
**Pre-deploy:** `python scripts/predeploy_alembic_check.py` — legacy DB + orders adat ellenőrzés (exit `2` = veszélyes).  
**Production pip:** `pip install -r requirements-prod.txt` (pinelt lock a zöld környezetből; PyJWT ≥ 2.13).  
**Jogi dokumentumok:** [production_legal_todo.md](./production_legal_todo.md) — ügyfél/jogász jóváhagyás szükséges.  
Éles viselkedés: **`MESENCSI_PRODUCTION=true`** → startup validator + Barion/CORS/SMTP kötelező mezők.

**Owner QA:** [pre_production_qa.md](./pre_production_qa.md) · [checkout_shipping_guest_qa.md](./checkout_shipping_guest_qa.md) · **Review:** [REVIEW_CHECKLIST.md](../../REVIEW_CHECKLIST.md) · **Ops:** [ops_runbook.md](./ops_runbook.md)

---

## Séma (025–032)

| Rev | Tartalom |
|-----|----------|
| `025` | Email lowercase, `users.token_version`, unique `lower(email)` |
| `026` | `email_outbox` tábla |
| `027` | `order_idempotency` tábla |
| `028` | CHECK constraints (products, orders, payment_attempts) |
| `029` | Outbox `claimed_at`, `next_retry_at` (atomic worker) |
| `030` | Guest checkout (`orders.user_id` nullable, guest idempotency) |
| `031` | `shipping_method`, `shipping_price`, `shipping_metadata_json` |
| `032` | Storybook page image layout |

## Szállítás (storefront)

- **Aktív:** személyes átvétel (0 Ft), GLS házhozszállítás (automatikus csomagméret / 2190–3290 Ft).
- **Foxpost:** jelenleg **nem aktív** — szerver 422, nincs a `/shop/config` listában.
- A szállítási díjat a backend számolja újra rendeléskor; a Barion összeg tartalmazza.
- Részletes QA: [checkout_shipping_guest_qa.md](./checkout_shipping_guest_qa.md).

---

## 1. Gyors env checklist (éles)

| Kötelező (production) | Megjegyzés |
|----------------------|------------|
| `MESENCSI_PRODUCTION=true` | Stub Barion tiltva; IPN titok kötelező |
| `USER_JWT_SECRET` | Shop JWT, ≥32 karakter, nem placeholder |
| `ADMIN_JWT_SECRET` | Admin JWT (`typ=admin`), **külön** a shop titoktól |
| `CORS_ALLOWED_ORIGINS` | Vesszővel; nincs `*`, localhost, `null`. Alias: `ALLOWED_ORIGINS` |
| `POSTGRES_*` | User, jelszó, host, db |
| `OWNER_*`, `MAINTENANCE_*` | **Saját** bcrypt hash — ne az `.env.example` alapértelmezett jelszó |
| `BARION_ENV=production` | (vagy `prod` / `live` / `release`) — **ne** maradjon `sandbox` élesben |
| `BARION_POS_KEY`, `BARION_PAYEE_EMAIL` | Üres POSKey = csak dev stub |
| `BARION_IPN_SECRET` | Production IPN auth (kötelező ha `MESENCSI_PRODUCTION=true`) |
| `BARION_BACKEND_PUBLIC_URL` | HTTPS publikus API |
| `BARION_RETURN_URL`, `BARION_CALLBACK_URL` | HTTPS (vagy épül a backend URL-ből) |
| `BARION_FRONTEND_LANDING_URL` | Bolt redirect return után |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Verify + fizetés-visszaigazoló levél |
| `PUBLIC_SITE_URL` / `FRONTEND_BASE_URL` | Linkek az e-mailekben |

| Ajánlott (production) | Megjegyzés |
|----------------------|------------|
| `REDIS_URL` | Több uvicorn worker / több instance: közös rate limit (`auth_limits.py`) |
| `TRUSTED_PROXY_HOSTS` | Reverse proxy IP/host (vesszővel). Alap: `127.0.0.1`. **`NE`** legyen nyilvános `*` élesben |
| `MEDIA_STORAGE=s3` + `MEDIA_PUBLIC_BASE_URL` | Ha nem persistent disk — lásd §5 |
| `ORDER_CONFIRMATION_PROCESSING_NOTE` | Feldolgozás / szállítás szöveg a fizetés-visszaigazoló levélben |
| `ENVIRONMENT=production` | Health válaszban |
| `INCIDENTS_READ_TOKEN` | Opcionális belső incidents |

**Indítás:** hiányzó/hibás éles env → `StartupConfigError` a logban, az app nem indul (`startup_config.py`).

Éles startup ellenőrzések (automatikus):

- `USER_JWT_SECRET` és `ADMIN_JWT_SECRET` **különböző**, min. 32 karakter, nem placeholder
- JWT algoritmus whitelist: `HS256` / `HS384` / `HS512`
- `OWNER_PASSWORD` / `MAINTENANCE_PASSWORD` — **valódi bcrypt hash**, nem az `.env.example` ismert placeholder
- `QA_SHOP_*` env **tiltva** élesben
- `PUBLIC_SITE_URL`, `BACKEND_PUBLIC_URL`, `FRONTEND_BASE_URL` — HTTPS
- SMTP teljes konfiguráció kötelező

**Shop CSRF:** A böngésző `POST`/`PATCH`/`DELETE` hívásokhoz `mesencsi_csrf` cookie + `X-CSRF-Token` fejléc kell (pl. fizetés újrapróbálás a Rendeléseim menüben). A frontend `GET /auth/csrf`-et hív induláskor és mentés előtt.

**JWT `token_version`:** Shop JWT tartalmaz `tv` claimet; jelszócsere / ban / verify bump → régi tokenek 401. Migráció: `025_user_email_token_version`.

**Order idempotency:** `POST /orders` opcionális `Idempotency-Key` fejléc (8–128 karakter, `[A-Za-z0-9_-]`). Ugyanazzal a kulccsal és tartalommal → ugyanaz a rendelés-csoport; más tartalommal → 409.

**Preset profilképek:** `/images/avatars/presets/preset-1.svg` … `preset-4.svg` — engedélyezett URL a szerver validációban (`image_upload.py`).

---

Részletes sandbox manuális teszt terv: [BARION_SANDBOX_TESTING.md](../../BARION_SANDBOX_TESTING.md).

## 2. Barion — sandbox vs éles

| | Sandbox / dev | Production |
|---|----------------|------------|
| Env | `BARION_ENV=sandbox` (alap) | `BARION_ENV=production` |
| API | `api.test.barion.com` | `api.barion.com` |
| POSKey | Teszt kulcs a Barion sandbox fiókból | Éles POSKey |
| Fizetés verify | `GetPaymentState` — egyetlen `paid` forrás | Ugyanaz |
| IPN | `BARION_IPN_SECRET` ajánlott; prod-ban **kötelező** | |
| Stub | Nincs `BARION_POS_KEY` → `preview-…` (csak ha **nincs** `MESENCSI_PRODUCTION`) | Tiltva |

Ellenőrzés deploy előtt: `GET /payments/barion/status` → `sandbox`, `pos_key_configured`, `rest_api_enabled`, `barion_ipn_secret_configured`.

**Fontos viselkedés (implementálva):**
- `paid` csak return / IPN / `GetPaymentState` után
- Duplicate `POST /payments/barion/start` pendingre → meglévő `payment_id` (nem ír felül)
- `POST /payments/barion/start` csak **teljes checkout csoportra** (minden sor ugyanabból a `checkout_group_id`-ból) — részleges csoport → **409**
- `POST /orders` **guest** (email a body-ban) vagy **email-verified** userrel; sikeres fizetés után **szerver oldali kosár ürítés** (bejelentkezett usernél)
- Admin: `completed` csak ha `payment_status=paid`
- Email címek **lowercase** tárolás + case-insensitive login (migráció `025`)

**Nyilvános staging:** Ha `MESENCSI_PRODUCTION=false` és nincs `BARION_IPN_SECRET`, az IPN **nem hitelesített** — állíts be titkot vagy ne tedd nyilvánosra a staging URL-t.

**Fejlesztői / manuális teszt (nem Barion IPN):**
- `POST /payments/barion/callback` — stub vagy REST GetPaymentState szinkron (élesben csak belső debug titokkal)
- `POST /payments/barion/webhook` — **elavult alias** ugyanarra

---

## 3. E-mail (SMTP)

**Render / staging:** [render_smtp.md](./render_smtp.md).

**Password reset:** `POST /auth/forgot-password`, `POST /auth/reset-password` — reset link: `FRONTEND_BASE_URL/reset-password.html?token=…`

| Flow | Mikor | SMTP nélkül |
|------|--------|-------------|
| Regisztráció verify | `POST /auth/register` | **Hosted:** startup blocker vagy **503**; **dev:** link a logban |
| **Fizetés visszaigazolás** | Barion verify → `paid` (IPN/return) | Nincs levél, rendelés `paid` marad |

**Email outbox (éles ajánlott):** A fizetés-visszaigazoló levél nem daemon threadben megy, hanem `email_outbox` táblába kerül (`026`, `029`). Cron / Render job:

```bash
python scripts/process_email_outbox.py [limit]
# exit 0 = ok, 1 = retriable fail, 2 = dead-letter, 3 = exception
# dead-letter újrapróbálás: python scripts/process_email_outbox.py --requeue-dead
```

Ajánlott: 1–5 percenként futtatni élesben. Részletek: [ops_runbook.md](./ops_runbook.md).

Helyi auth e-mail QA: [local_auth_email_qa.md](./local_auth_email_qa.md).

---

## 4. CORS

- **Dev:** nincs env → localhost / 127.0.0.1 alapértelmezés (`cors_config.py`).
- **Production:** csak `CORS_ALLOWED_ORIGINS`; wildcard és localhost **tiltva** (startup blocker).
- **Same-origin deploy** (FastAPI szolgálja a `frontend/`-et): `allow_credentials=False` rendben. Külön frontend origin esetén CORS + credentials együtt kell.

---

## 5. Média / Render

- Feltöltések: **`backend/media/uploads/`** — URL: `/media/uploads/…`
- Statikus bolt dekor: **`frontend/images/`** (pl. preset avatárok) — nem vesznek el restartnál
- **Render / ephemeral disk:** feltöltött admin képek **elveszhetnek** restart után
  - **Megoldás A:** persistent volume a `media/uploads` útvonalra
  - **Megoldás B:** `MEDIA_STORAGE=s3` + `MEDIA_PUBLIC_BASE_URL` (`media_storage.py`)
- Deploy előtt: `media/uploads` létezik és **írható** (`GET /health/business` → `media_uploads.ok`)

---

## 6. Admin auth

- `POST /admin/login` → JWT (`ADMIN_JWT_SECRET`), HttpOnly cookie
- Szerepkörök: `owner` (teljes), `maintenance` (korlátozott írás)
- Jelszavak: bcrypt hash az `.env`-ben (`scripts/setup_admin_credentials.py`)

**Owner-only műveletek** (maintenance → 403):

- Shop user verify / ban / unban / delete
- Rendelés sor törlése
- `payment_status` módosítás

**Vásárlói fiókok:** `GET /admin/shop-users`, soft delete, verify/ban, személyes kupon (owner).

---

## 7. Health & monitoring

| Útvonal | Használat |
|---------|-----------|
| `GET /health` | Liveness |
| `GET /health/business` | Admin JWT; `static_frontend`, `media_uploads` |

---

## 8. Pytest (deploy előtt)

```bash
cd backend
python -m pip install -r requirements.txt -r requirements-dev.txt
python scripts/predeploy_alembic_check.py
python -m alembic upgrade head
python -m pytest -q
```

Várható: **347 passed**, néhány skip (pl. Postgres smoke ha nincs DB).

Opcionális:

- `scripts/gate_pytest.ps1`
- `pip-audit` (requirements-prod lock ellenőrzés)
- Postgres: `python scripts/postgres_smoke.py` vagy `pytest tests/test_postgres_alembic_smoke.py`
- E2E Playwright (`npm test` az `e2e/` mappában)

---

## 9. Manuális smoke — ajánlott sorrend (~30 perc)

1. [ ] `python scripts/predeploy_alembic_check.py` → ok
2. [ ] `alembic upgrade head` → head = **`032`**
3. [ ] Szerver indul éles envvel (nincs `StartupConfigError`)
4. [ ] `GET /health` → 200
5. [ ] `GET /health/business` (admin JWT) → `static_frontend.ok`, `media_uploads.ok`
6. [ ] `GET /` — storefront
7. [ ] `GET /payments/barion/status`
8. [ ] Regisztráció → verify → login (email case-insensitive)
9. [ ] Kosár → checkout → `POST /orders` → kosár üres a szerveren
10. [ ] Dupla `POST /orders` ugyanazzal `Idempotency-Key`-vel → nem duplikál
11. [ ] `POST /payments/barion/start` → Barion (teljes checkout csoport)
12. [ ] Fizetés → `payment_status=paid`
13. [ ] IPN log: `barion_orders_synced`
14. [ ] `email_outbox` sor + `process_email_outbox.py` → visszaigazoló levél
15. [ ] Rendeléseim: szállítás + megjegyzés; fizetés újrapróbálás (CSRF)
16. [ ] Admin owner: rendeléslista; `completed` csak paid mellett; maintenance nem módosíthat `payment_status`-t
17. [ ] Jelszócsere után régi shop JWT 401
18. [ ] CORS / auth smoke (lásd [pre_production_qa.md](./pre_production_qa.md))

---

## 10. Deploy parancsok

```bash
docker compose up -d
copy .env.example .env
run.bat
```

Éles:

```bash
pip install -r requirements-prod.txt
python scripts/predeploy_alembic_check.py
alembic upgrade head
# uvicorn / gunicorn — app indul
# cron: python scripts/process_email_outbox.py
```

`MESENCSI_PRODUCTION=true`; HTTPS reverse proxy; `TRUSTED_PROXY_HOSTS` = proxy IP; több worker → `REDIS_URL`.

---

## 11. Mit nem csinál a checklist helyetted

- Barion merchant / POS regisztráció
- DNS + TLS
- SMTP szolgáltató / domain SPF-DKIM
- Owner manuális QA aláírás
- Szállítási díj / futár API (üzleti döntés — jelenleg ár tartalmazza a szállítást)
