# Mesencsi Gate — teljes pre-production (pytest + E2E)
$ErrorActionPreference = "Stop"
$Scripts = $PSScriptRoot

Write-Host "=== Gate: FULL (pytest + E2E) ===" -ForegroundColor Cyan
& (Join-Path $Scripts "gate_pytest.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $Scripts "gate_e2e.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "OK: full gate passed." -ForegroundColor Green
