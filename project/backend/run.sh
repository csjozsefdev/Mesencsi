#!/usr/bin/env bash
# Same Python for pip + uvicorn + alembic (use from project root: bash run.sh)
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "Creating virtual environment in .venv ..."
  python3 -m venv .venv
fi

echo "Installing dependencies ..."
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "Applying database migrations ..."
.venv/bin/python -m alembic upgrade head

echo "Starting API ..."
# Storefront + admin: http://127.0.0.1:8000/ and http://127.0.0.1:8000/admin
exec .venv/bin/python -m uvicorn mesencsi:app --host 127.0.0.1 --port 8000 --reload
