# Mesencsi Gate parancsok

## Ajánlott Gate rend (fix)

| Lépés | Mikor | Parancs / teendő |
|-------|--------|------------------|
| **1** | Minden commit előtt | `.\scripts\gate_pytest.ps1` |
| **2** | E2E első lokális validálás | Node + npm; backend fut; `/` + `/admin/login` OK → `cd ..\e2e` → `npm test` |
| **3** | Release / pre-production | `.\scripts\gate_full.ps1` |
| **4** | Manuális QA (kötelező) | Barion sandbox, SMTP, admin rendelés, storybook upload/preview, mobil |

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

További részletek: [E2E_TESTING.md](../../E2E_TESTING.md), [deploy_readiness.md](deploy_readiness.md).
