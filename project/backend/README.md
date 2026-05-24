# Mesencsi — backend (FastAPI)

**English handover / review:** see [HANDOVER.md](../HANDOVER.md) and [REVIEW_CHECKLIST.md](../REVIEW_CHECKLIST.md) in the project root.

## Gyors indítás (ajánlott, Windows)

1. **Docker Desktop** telepítve legyen (Postgres a `docker-compose` miatt kell).
2. Másold a **`.env.example`** fájlt **`.env`** névre ugyanebben a mappában, és állíts be jelszót a `POSTGRES_PASSWORD` mezőben (és egyeztess a compose-szal, ha módosítod a felhasználót is).
3. Indítsd a Postgres konténert:
   ```bat
   docker compose up -d
   ```
4. A backend mappában futtasd:
   ```bat
   .\run.bat
   ```

A `run.bat` létrehozza a **`.venv`** környezetet (ha kell), telepíti a függőségeket, lefuttatja az **Alembic** migrációkat, majd elindítja az Uvicorn-t **ugyanazzal a Pythonnal** (elkerüli a „ModuleNotFoundError: sqlalchemy” típusú PATH / két Python keveredést).

- Bolt + admin böngészőben: `http://127.0.0.1:8000/` és `http://127.0.0.1:8000/admin`

## Port 8000 foglalt

A `run.bat` indulás előtt ellenőrzi: ha a **8000-as** portot már egy másik folyamat foglalja, és az **nem** ennek a projektnek a `.venv\Scripts\python.exe` folyamata, **nem** indul el a szerver, és kiírja a foglaló PID-et / elérési utat.

Tipikus ok: globálisan telepített **`uvicorn`** fut másik Pythonnal. Megoldás: állítsd le azt a folyamatot, vagy használd a projekt wrappert:

```bat
.\uvicorn.bat mesencsi:app --reload --host 127.0.0.1 --port 8000
```

Ha a portot a **`.venv` Python** foglalja, valószínűleg már fut egy példány — állítsd le, vagy módosítsd a `run.bat` utolsó sorában a `--port` értékét.

## Manuális lépések (ha nem `run.bat`)

Ugyanebből a mappából, **ugyanazzal a `python.exe`-vel** minden parancs:

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn mesencsi:app --host 127.0.0.1 --port 8000 --reload
```

## CORS / frontend más porton

A fejlesztői CORS beállítások a `mesencsi.py`-ban vannak (pl. Vite `5173`, Live Server `5500`). Éles környezetben szűkítsd az `allow_origins` listát.
