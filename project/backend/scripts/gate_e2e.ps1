# Mesencsi Gate — Playwright E2E (lassúbb, külön a pytest-től)
$ErrorActionPreference = "Stop"
$E2eRoot = Join-Path $PSScriptRoot "..\..\e2e"
$BackendRoot = $PSScriptRoot\..

Write-Host "=== Gate: E2E (Playwright) ===" -ForegroundColor Cyan

# Backend health
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -ne 200) {
        Write-Host "HIBA: /health nem 200. Indítsd: backend\run.bat" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "HIBA: Backend nem fut (http://127.0.0.1:8000). Indítsd: backend\run.bat" -ForegroundColor Red
    exit 1
}

Set-Location $E2eRoot
if (-not (Test-Path "node_modules")) {
    Write-Host "npm install (e2e)..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if (-not (Test-Path (Join-Path $env:USERPROFILE ".cache\ms-playwright"))) {
    Write-Host "playwright install chromium..." -ForegroundColor Yellow
    npx playwright install chromium
}

$py = Join-Path $BackendRoot ".venv\Scripts\python.exe"
& $py (Join-Path $BackendRoot "scripts\ensure_frontend_assets.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

npm test
exit $LASTEXITCODE
