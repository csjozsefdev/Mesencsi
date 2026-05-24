# Media / uploads persistence smoke (Render)

**Figyelmeztetés:** `media/uploads/` alapból **helyi lemez** — Render ephemeral disk esetén deploy/restart után a feltöltött fájlok **elveszhetnek**.

## Gyors ellenőrzés (szerveren vagy helyben)

```powershell
cd backend
# 1) Könyvtár létezik és írható
python -c "from image_upload import UPLOADS_ROOT; from health_service import _dir_writable_ok; ok, d = _dir_writable_ok(UPLOADS_ROOT); print('uploads', UPLOADS_ROOT, d, ok)"
```

Vagy API-n keresztül (admin JWT):

- `GET /health/business` → `components.media_uploads.detail` = `ok`

## Persistence teszt (ha van persistent disk / volume)

1. Admin: tölts fel egy kis galéria képet → jegyezd fel az URL-t (`/media/uploads/gallery/…`).
2. Nyisd meg a URL-t böngészőben — kép látszik.
3. **Restart** az app service-t (Render: Manual Deploy vagy restart).
4. Ugyanaz az URL újra — **kép még mindig látszik** = persistence OK.
5. Ha 404 / üres → **nincs** perzisztens tároló — éles előtt volume vagy S3/R2 terv kell.

## Mit ne törölj

- Ne futtass tömeges cleanup scriptet user feltöltésekre.
- Teszt fájlokat csak dedikált teszt prefix-szel (`pytest-`, `gallery-test-`) törölj, ha egyáltalán.

## Éles ajánlás

- Render **Persistent Disk** mount → `media/uploads`, **vagy**
- Object storage (S3/R2) későbbi milestone — jelenleg nincs migrálva.
