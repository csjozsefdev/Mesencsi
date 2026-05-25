# Mesencsi — deploy readiness (praktikus checklist)

Utolsó séma: **Alembic `021_product_bundle_discounts`** (`alembic upgrade head`).  
Éles viselkedés: **`MESENCSI_PRODUCTION=true`** → startup validator + Barion/CORS/SMTP kötelező mezők.

---

## 1. Gyors env checklist (éles)

| Kötelező (production) | Megjegyzés |
|----------------------|------------|
| `MESENCSI_PRODUCTION=true` | Stub Barion tiltva; IPN titok kötelező |
| `USER_JWT_SECRET` | Shop JWT, ≥32 karakter, nem placeholder |
| `ADMIN_JWT_SECRET` | Admin JWT (`typ=admin`), **külön** a shop titoktól |
| `CORS_ALLOWED_ORIGINS` | Vesszővel; nincs `*`, localhost, `null`. Alias: `ALLOWED_ORIGINS` |
| `POSTGRES_*` | User, jelszó, host, db |
| `OWNER_*`, `MAINTENANCE_*` | Bcrypt hash a `.env.example` szerint |
| `BARION_ENV=production` | (vagy `prod` / `live` / `release`) — **ne** maradjon `sandbox` élesben |
| `BARION_POS_KEY`, `BARION_PAYEE_EMAIL` | Üres POSKey = csak dev stub |
| `BARION_IPN_SECRET` | Production IPN auth |
| `BARION_BACKEND_PUBLIC_URL` | HTTPS publikus API |
| `BARION_RETURN_URL`, `BARION_CALLBACK_URL` | HTTPS (vagy épül a backend URL-ből) |
| `BARION_FRONTEND_LANDING_URL` | Bolt redirect return után |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Verify + fizetés-visszaigazoló levél |
| `PUBLIC_SITE_URL` / `FRONTEND_BASE_URL` | Linkek az e-mailekben |

Opcionális: `ORDER_CONFIRMATION_PROCESSING_NOTE`, `ENVIRONMENT=production`, `INCIDENTS_READ_TOKEN`.

**Indítás:** hiányzó/hibás éles env → `StartupConfigError` a logban, az app nem indul (`startup_config.py`).

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
- `POST /orders` csak **email-verified** userrel
- Admin: `completed` csak ha `payment_status=paid`

**Fejlesztői / manuális teszt (nem Barion IPN):**
- `POST /payments/barion/callback` — stub vagy REST GetPaymentState szinkron (élesben csak belső debug titokkal)
- `POST /payments/barion/webhook` — **elavult alias** ugyanarra; új integráció: a `/callback` útvonalat használja

---

## 3. E-mail (SMTP)

**Render / staging:** kötelező env és hibakezelés — [render_smtp.md](./render_smtp.md).

| Flow | Mikor | SMTP nélkül |
|------|--------|-------------|
| Regisztráció verify | `POST /auth/register` | **Hosted:** startup blocker vagy **503**; **dev:** link a logban |
| **Fizetés visszaigazolás** | Barion verify → `paid` (IPN/return), **nem** a frontend redirect önmagában | Nincs levél, rendelés `paid` marad |

Sikeres fizetés után: `payment_confirmation_email_sent` log. Duplikált IPN nem küld dupla levelet. SMTP hiba **nem** állítja vissza a fizetést.

Helyi teszt: `docker compose up -d` → Mailpit (`SMTP_HOST=127.0.0.1`, `SMTP_PORT=1025`, `SMTP_USE_TLS=0`), UI: `http://127.0.0.1:8025`.

Opcionális staging QA bolt user: `QA_SHOP_EMAIL` + `QA_SHOP_PASSWORD` (email verified induláskor).

---

## 4. CORS

- **Dev:** nincs env → localhost / 127.0.0.1 alapértelmezés (`cors_config.py`).
- **Production:** csak `CORS_ALLOWED_ORIGINS` (vagy `ALLOWED_ORIGINS`); wildcard és localhost **tiltva** (startup blocker).

---

## 5. Média / Render

- Feltöltések: **`backend/media/uploads/`** (galéria, termék, storybook, avatar) — URL: `/media/uploads/…`
- A FastAPI egy processzben szolgálja ki a `frontend/` statikus fájlokat is (`/`, CSS/JS, `frontend/images/` dekor képek).
- **Render / ephemeral disk:** restart után a feltöltött képek **elveszhetnek**, ha nincs persistent disk vagy külső storage (S3/R2). Éles deploynál: volume **vagy** object storage terv.
- Deploy előtt: `media/uploads` létezik és **írható** (ugyanaz az útvonal, mint `image_upload.UPLOADS_ROOT`).

---

## 6. Admin auth

- `POST /admin/login` → **JWT** (`ADMIN_JWT_SECRET`), nem `username|role` string.
- Szerepkörök: `owner` (teljes), `maintenance` (korlátozott, pl. nincs termék create).
- Jelszavak: `OWNER_PASSWORD` / `MAINTENANCE_PASSWORD` bcrypt hash az `.env`-ben.

**Vásárlói fiókok (admin UI):**

| Művelet | Endpoint |
|---------|----------|
| Lista | `GET /admin/shop-users` |
| Soft delete | `DELETE /admin/users/{id}` |
| Verify / ban / unban | `PATCH /admin/users/{id}/verify`, `/ban`, `/unban` |
| Személyes kupon | `POST /admin/users/{id}/discounts` |

A régi `GET /admin/users` lista duplikátum **nincs** — csak a `/shop-users` listázás.

---

## 7. Health & monitoring

| Útvonal | Használat |
|---------|-----------|
| `GET /health` | UptimeRobot / liveness (nyilvános) |
| `GET /health/business` | Belső / CI; **admin JWT** kell; ne külső monitor cél |

`ENVIRONMENT` vagy `ENV` → válaszban `environment` mező.

**`GET /health/business` — `components` (fájlrendszer, titok nélkül):**

| Kulcs | Mit néz | `detail` értékek |
|-------|---------|------------------|
| `static_frontend` | `frontend/` + `mesencsi.html` | `ok`, `missing`, `incomplete` |
| `media_uploads` | `media/uploads` írhatóság (probe fájl) | `ok`, `missing`, `not_writable` |

- Mindkettő OK + DB + admin JWT roundtrip OK → `status: "ok"`.
- `media_uploads` hiányzik vagy nem írható → `status: "degraded"`.
- `static_frontend` hiányos → `status: "degraded"`.

Példa (részlet): `components.static_frontend.ok`, `components.media_uploads.detail`.

---

## 8. Pytest (deploy előtt)

```bash
cd backend
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest -q
```

- Teszt DB: SQLite memória (`tests/conftest.py`), nem kell éles Postgres a pytesthez.
- Barion HTTP: mock; integráció: `test_barion_*`, `test_checkout_bundle_integration`, `test_payment_confirmation_email`, `test_admin_jwt_auth`, `test_cors_config`, `test_startup_config`, `test_health_media`.

---

## 9. Manuális smoke — ajánlott sorrend (~20 perc)

1. [ ] `alembic upgrade head` → head = `021`
2. [ ] Szerver indul éles envvel (nincs `StartupConfigError`)
3. [ ] `GET /health` → 200
4. [ ] `GET /health/business` (admin JWT) → `static_frontend.ok`, `media_uploads.ok`, `status: ok`
5. [ ] `GET /` — storefront betölt
6. [ ] `GET /payments/barion/status` — Barion env ellenőrzés
7. [ ] Regisztráció → verify e-mail (Mailpit/SMTP) → login
8. [ ] Kosár → checkout → **`POST /orders`** (verified user)
9. [ ] **`POST /payments/barion/start`** → Barion (sandbox vagy éles)
10. [ ] Fizetés befejezése → return URL → DB: `payment_status=paid`
11. [ ] IPN érkezik (log: `barion_orders_synced`)
12. [ ] **Visszaigazoló e-mail** megérkezett (sikertelen fizetésnél **ne** legyen)
13. [ ] Dupla return/IPN → **egy** e-mail
14. [ ] `GET /orders` — rendelés látszik
15. [ ] `/admin/login` → JWT → rendeléslista; `completed` csak paid mellett
16. [ ] Galéria kép URL; admin kis feltöltés
17. [ ] CORS: más originről API hívás **tiltva** (prod domainről OK)
18. [ ] `GET /admin/shop-users` token nélkül → 401

---

## 10. Deploy parancsok (helyi / VPS)

```bash
docker compose up -d          # Postgres + Mailpit (dev)
copy .env.example .env        # kitöltés
run.bat                       # venv + migrate + uvicorn :8000
```

Éles: **ne** `--reload`; uvicorn worker(ek); `MESENCSI_PRODUCTION=true`; HTTPS reverse proxy (Caddy/nginx) a Barion return/IPN URL-ekhez.

---

## 11. Mit nem csinál a checklist helyetted

- Barion merchant / POS regisztráció a Barion felületén
- DNS + TLS tanúsítvány
- Render persistent disk / S3 bekötés
- CI pipeline beállítás (csak pytest parancs fent)
