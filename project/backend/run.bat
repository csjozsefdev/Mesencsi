@echo off
REM Same Python for pip + uvicorn (avoids "ModuleNotFoundError: sqlalchemy" when PATH uses another python).
REM In PowerShell run:  .\run.bat   (not "run.bat" alone — current directory is not on PATH.)
REM Docker: install Docker Desktop if "docker" is not recognized; then: docker compose up -d
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment in .venv ...
  python -m venv .venv
  if errorlevel 1 exit /b 1
)

echo Installing dependencies ...
".venv\Scripts\python.exe" -m pip install -q --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

REM C: Ha a 8000-at mar egy masik (pl. rendszer-) Python/uvicorn foglalja, ne induljunk el hibas ertekelessel.
echo Checking TCP port 8000 ...
set "MESENC_BACKEND_ROOT=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$r=$env:MESENC_BACKEND_ROOT.TrimEnd('\\'); $p=8000; $wp=Join-Path $r '.venv\Scripts\python.exe'; $w=$null; if (Test-Path -LiteralPath $wp) { $w=(Resolve-Path -LiteralPath $wp).Path }; $n=@(Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue); if ($n.Count -eq 0) { exit 0 }; $id=$n[0].OwningProcess; $pr=Get-CimInstance Win32_Process -Filter ('ProcessId='+$id) -ErrorAction SilentlyContinue; if (-not $pr) { Write-Host ('A(z) {0}-as port foglalt (PID {1}), de a folyamat reszletei nem olvashatok.' -f $p,$id) -ForegroundColor Red; exit 1 }; $ex=[string]$pr.ExecutablePath; if ($w -and ($ex -ieq $w)) { Write-Host ('Figyelem: a {0}-as portot mar foglalja ez a projekt .venv Pythonja (PID {1}). Allitsd le a masik uvicorn-t, vagy valtoztasd a portot a run.bat vegen.' -f $p,$id) -ForegroundColor Yellow; exit 1 }; Write-Host ('HIBA: a {0}-as portot mas folyamat foglalja.' -f $p) -ForegroundColor Red; Write-Host ('  PID {0}: {1}' -f $id,$ex); $cl=[string]$pr.CommandLine; if ($cl) { Write-Host ('  CommandLine: {0}' -f $cl) }; if ($w) { Write-Host ('  Ehhez a projekthez varhato .venv: {0}' -f $w) }; Write-Host ('  Allitsd le a foglalo folyamatot (pl. taskkill /PID {0} /F), vagy valtoztasd meg a portot a run.bat vegen.' -f $id); exit 1"
if errorlevel 1 exit /b 1

echo Applying database migrations ...
".venv\Scripts\python.exe" -m alembic upgrade head
if errorlevel 1 (
  echo Alembic failed. Start Postgres first, e.g.: docker compose up -d
  exit /b 1
)

echo Checking storefront assets (mesencsi-bg.jpg + favicons) ...
".venv\Scripts\python.exe" scripts\ensure_frontend_assets.py
if errorlevel 1 exit /b 1

echo Starting API ...
REM --reload-delay reduces flaky KeyboardInterrupt traces on Windows when many files save at once.
REM Storefront + admin: http://127.0.0.1:8000/  és  http://127.0.0.1:8000/admin
".venv\Scripts\python.exe" -m uvicorn mesencsi:app --host 127.0.0.1 --port 8000 --reload --reload-delay 2
