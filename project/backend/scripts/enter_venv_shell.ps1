# Opcionális: PowerShell-ben venv PATH + prompt, script tiltás nélkül (csak erre a folyamatra).
# Futtatás a backend mappából:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\enter_venv_shell.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
& "$root\.venv\Scripts\Activate.ps1"
Write-Host "Venv aktív (csak ebben a PowerShell ablakban). Kilépés: deactivate" -ForegroundColor Green
