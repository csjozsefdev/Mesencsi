@echo off
REM Local uvicorn wrapper: always use project venv (avoids system-Python mismatch).
REM Usage (from this folder): uvicorn mesencsi:app --reload --host 127.0.0.1 --port 8000
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv. Run .\run.bat once to create it.
  exit /b 1
)

".venv\Scripts\python.exe" -m uvicorn %*
