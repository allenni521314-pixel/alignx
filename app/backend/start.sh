#!/usr/bin/env sh
set -eu

DB_FILE="$(printf '%s' "${DATABASE_URL:-sqlite+aiosqlite:////data/sql_app.db}" | sed -n 's#^sqlite[^:]*:////#/#p')"
if [ -z "$DB_FILE" ]; then
  DB_FILE="/data/sql_app.db"
fi

mkdir -p "$(dirname "$DB_FILE")"

if [ ! -f "$DB_FILE" ] && [ -f "/app/sql_app.db" ]; then
  cp /app/sql_app.db "$DB_FILE"
elif [ ! -f "$DB_FILE" ] && [ -f "./sql_app.db" ]; then
  cp ./sql_app.db "$DB_FILE"
fi

PYTHON_BIN="${PYTHON:-python}"
exec "$PYTHON_BIN" -m uvicorn main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
