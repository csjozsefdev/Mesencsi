@echo off
REM Local pip wrapper: always use project venv (avoids installing into system Python).
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv. Run .\run.bat once to create it.
  exit /b 1
)

".venv\Scripts\python.exe" -m pip %*
