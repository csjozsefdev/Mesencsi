# Mesencsi Gate parancsok

## Ajánlott Gate rend (fix)

| Lépés | Mikor | Parancs / teendő |
|-------|--------|------------------|
| **1** | Minden commit előtt | `.\scripts\gate_pytest.ps1` |
| **2** | E2E első lokális validálás | Node + npm; backend fut; `/` + `/admin/login` OK → `cd ..\e2e` → `npm test` |
| **3** | Deploy előtt (DB) | `python scripts/predeploy_alembic_check.py` → `alembic upgrade head` |
| **4** | Release / pre-production | `.\scripts\gate_full.ps1` |
| **5** | Manuális QA (kötelező) | Barion sandbox, SMTP + outbox, admin rendelés, storybook, mobil |

**E2E GO** az infrastruktúrára; zöld E2E futás csak érvényes, ha Node/npm + futó backend + dev `.env` (nem production).

## Scriptek

| Script | Tartalom |
|--------|----------|
| `scripts/gate_pytest.ps1` | Backend pytest (`pytest -q`) |
| `scripts/gate_e2e.ps1` | `/health` + Playwright E2E (`e2e/`) |
| `scripts/gate_full.ps1` | pytest → E2E sorban |

Futtatás a `backend` mappából:

```powershell
.\scripts\gate_pytest.ps1
.\scripts\gate_e2e.ps1
.\scripts\gate_full.ps1
```

Opcionális éles előtt:

```powershell
pip install -r requirements-prod.txt
pip-audit -r requirements-prod.txt
python scripts/postgres_smoke.py   # ha van Postgres
python scripts/process_email_outbox.py   # outbox smoke
```

További részletek: [E2E_TESTING.md](../../E2E_TESTING.md), [deploy_readiness.md](deploy_readiness.md), [ops_runbook.md](ops_runbook.md).
