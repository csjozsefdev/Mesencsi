# Mesencsi — Playwright E2E tesztelés

A **backend pytest** (`backend/tests/`) és az **E2E** (`e2e/`) külön futnak. Az E2E a futó FastAPI szervert használja (ugyanaz a Postgres/SQLite, mint a `.env`).

## Ajánlott Gate rend (fix)

| Lépés | Mikor | Teendő |
|-------|--------|--------|
| **1** | Minden commit előtt | `backend\scripts\gate_pytest.ps1` |
| **2** | E2E első lokális validálás | Node + npm telepítve, backend fut, storefront + admin elérhető → `cd e2e` → `npm test` |
| **3** | Deploy előtt (DB) | `python scripts/predeploy_alembic_check.py` → `alembic upgrade head` (head: **029**) |
| **4** | Release / pre-production előtt | `backend\scripts\gate_full.ps1` (pytest, majd E2E) |
| **5** | Manuális QA (kötelező) | Barion sandbox, SMTP + email outbox, admin rendelés, storybook, mobil |

**E2E infrastruktúra: GO** — az E2E eredmény csak akkor érvényes, ha Node/npm telepítve van, a backend fut, és a megfelelő dev test env aktív (nem production DB).

Az E2E **nem** fut automatikusan a pytest mellett (lassú, böngésző + szerver kell).

### E2E pre-flight (~30 mp)

- [ ] `uvicorn` / `run.bat` fut → `GET http://127.0.0.1:8000/health` → 200
- [ ] `http://127.0.0.1:8000/` és `/admin/login` betölt
- [ ] `node -v` és `npm -v` működik
- [ ] `cd e2e` → `npm test`

### Manuális QA (4. lépés) — „kész” jelentése

- **Barion sandbox:** pending → fizetés → `paid`; max. egy visszaigazoló e-mail — [BARION_SANDBOX_TESTING.md](BARION_SANDBOX_TESTING.md)
- **SMTP + outbox:** regisztrációs verify + `process_email_outbox.py` → fizetés utáni levél
- **Admin:** rendeléslista; `completed` csak `paid` mellett
- **Storybook:** admin szerkesztés + publikus olvasó / preview
- **Mobil (~768px):** menü, kosár FAB, háttérkép, nincs kritikus layout törés

## Gate parancsok (részletek)

| Parancs | Tartalom |
|---------|----------|
| `backend\scripts\gate_pytest.ps1` | Csak pytest (`pytest -q`) |
| `backend\scripts\gate_e2e.ps1` | Health check + Playwright (`e2e/`, backend már fut) |
| `backend\scripts\gate_full.ps1` | pytest → E2E sorban |

## Előfeltétel

1. Backend fut: `cd backend` → `run.bat` vagy  
   `.venv\Scripts\python.exe -m uvicorn mesencsi:app --host 127.0.0.1 --port 8000`
2. `alembic upgrade head` (Postgres / dev DB)
3. Backend `.env`:
   - `USER_JWT_SECRET`, `ADMIN_JWT_SECRET` (pytest gate-hez is)
   - `OWNER_USERNAME` / `OWNER_PASSWORD` — E2E admin: alapértelmezett jelszó a `.env.example` szerint: **`jelszó`**
4. `frontend/images/mesencsi-bg.jpg` létezik (`scripts/ensure_frontend_assets.py`)

## E2E első telepítés

```powershell
cd e2e
npm install
npx playwright install chromium
copy .env.example .env
```

## Futtatás

```powershell
# Backend külön ablakban fut

cd e2e
npm test
npm run test:headed
npm run test:ui
npm run test:debug
npm run report
```

Gate (pytest + health + E2E):

```powershell
cd backend
.\scripts\gate_e2e.ps1
.\scripts\gate_full.ps1
```

Opcionális: Playwright indítsa a szervert (`e2e/.env`):

```
E2E_START_SERVER=true
```

## Env változók (`e2e/.env`)

| Változó | Alapértelmezés |
|---------|----------------|
| `E2E_BASE_URL` | `http://127.0.0.1:8000` |
| `E2E_USER_EMAIL` | `e2e-buyer@mesencsi.test` |
| `E2E_USER_PASSWORD` | `E2eTest1234!` |
| `E2E_ADMIN_USER` | `owner` |
| `E2E_ADMIN_PASSWORD` | `jelszó` |
| `E2E_TRACE` | `on-first-retry` |
| `E2E_VIDEO` | `off` |

## Tesztadat forrása

- **Shop user:** `global-setup.ts` → `POST /auth/register` (409 OK) → `scripts/dev_manual_verify_shop_user.py` (meglévő dev script, nem új seed rendszer)
- **Session:** `e2e/.auth/shop-user.json`, `admin-owner.json` (gitignore)
- **Admin:** `POST /admin/login` — ha `ADMIN_JWT_SECRET` hiányzik, admin tesztek skip

**Nem** production DB. **Nem** pytest SQLite memória.

## Lefedett flow-k (smoke)

- Publikus főoldal, navigáció, galéria, háttérkép
- Kijelentkezett: rejtett webshop/kosár FAB
- Login / logout, védett menük
- Admin login, dashboard, menük, hírek modul
- Webshop, kosár, add-to-cart (ha van termék)
- Checkout UI látható — **nincs** Barion fizetés indítás
- Barion stub query (`?payment=barion&pid=preview-…`) nem omlik össze

## Kimaradt / szándékos határ

- Valódi Barion Payment/Start és IPN
- SMTP / e-mail inbox
- Fájlfeltöltés (galéria admin upload)
- Postgres-only smoke (marad pytest marker)
- Mobil viewport teljes mátrix
- Teljes checkout POST /orders + paid állapot

## Hibakeresés

- Screenshot + trace: `e2e/test-results/`, `e2e/playwright-report/`
- Trace: `E2E_TRACE=on` majd `npx playwright show-trace …`
- Headed: `npm run test:headed`

## Ismert limitációk

- Üres terméklista → add-to-cart / checkout tesztek **skip**
- Admin tesztek **skip**, ha nincs `ADMIN_JWT_SECRET` / rossz owner jelszó
- `Mesekönyvek` menü csak akkor látszik, ha van közzétett könyv + bejelentkezés
