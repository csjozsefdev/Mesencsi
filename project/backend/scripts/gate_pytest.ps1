# Mesencsi Gate — backend pytest (gyors, nincs Playwright)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== Gate: pytest (backend) ===" -ForegroundColor Cyan
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "HIBA: .venv hiányzik. Futtasd: run.bat vagy python -m venv .venv" -ForegroundColor Red
    exit 1
}
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "OK: pytest gate passed." -ForegroundColor Green
