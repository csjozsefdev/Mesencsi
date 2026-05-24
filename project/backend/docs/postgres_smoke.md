# Postgres smoke (manuális QA előtt)

A default `pytest` **SQLite memóriában** fut (`tests/conftest.py`). Ez szándékos — gyors CI.

## Mikor futtasd

- Deploy előtt, ha van elérhető Postgres (Docker, Render preview DB, helyi).
- Séma + driver + alap query ellenőrzés.

## Előfeltétel

- Postgres szerver fut.
- Üres vagy dedikált teszt adatbázis (pl. `mesencsi_test`).

## Parancsok (PowerShell)

```powershell
cd backend
$env:MESENCSI_POSTGRES_SMOKE_URL = "postgresql+psycopg://mesencsi:jelszo@localhost:5432/mesencsi_test"
python scripts/postgres_smoke.py
```

A script:

1. `alembic upgrade head` a megadott URL-en
2. `pytest tests/test_postgres_smoke.py -m postgres`

## Csak pytest (ha az env már be van állítva)

```powershell
$env:MESENCSI_TEST_DATABASE_URL = $env:MESENCSI_POSTGRES_SMOKE_URL
python -m alembic upgrade head
python -m pytest tests/test_postgres_smoke.py -m postgres -q
```

## Várható eredmény

- `OK: Postgres smoke passed.`
- 3 teszt zöld (connect, health, users tábla)

Ha nincs Postgres, **kihagyható** — a SQLite suite továbbra is a fő Gate 1 automata teszt.
