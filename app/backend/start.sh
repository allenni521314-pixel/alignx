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

export HERMES_HOME="${HERMES_HOME:-/data/.hermes}"
export HERMES_AGENT_URL="${HERMES_AGENT_URL:-http://127.0.0.1:9120}"
mkdir -p "$HERMES_HOME"

AI_PROVIDER_LC="$(printf '%s' "${AI_PROVIDER:-}" | tr '[:upper:]' '[:lower:]')"
case "${AI_PROVIDER_LC}:${OPENAI_BASE_URL:-}" in
  *qwen*|*dashscope*)
    HERMES_MODEL_API_KEY="${HERMES_MODEL_API_KEY:-${VISION_API_KEY:-${DASHSCOPE_API_KEY:-${QWEN_API_KEY:-${OPENAI_API_KEY:-${APP_AI_KEY:-}}}}}}"
    ;;
  *)
    HERMES_MODEL_API_KEY="${HERMES_MODEL_API_KEY:-${OPENAI_API_KEY:-${APP_AI_KEY:-${DASHSCOPE_API_KEY:-${QWEN_API_KEY:-${VISION_API_KEY:-}}}}}}"
    ;;
esac

if [ "${HERMES_MANAGED_CONFIG:-true}" != "false" ]; then
  cat > "$HERMES_HOME/config.yaml" <<EOF
model:
  provider: custom
  base_url: "${OPENAI_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
  default: "${AI_DEFAULT_MODEL:-qwen3-32b}"
  api_key: "${HERMES_MODEL_API_KEY:-}"
  api_mode: "${HERMES_AI_API_MODE:-chat_completions}"
custom_providers:
  - name: alignx-ai
    base_url: "${OPENAI_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
    api_key: "${HERMES_MODEL_API_KEY:-}"
    api_mode: "${HERMES_AI_API_MODE:-chat_completions}"
    model: "${AI_DEFAULT_MODEL:-qwen3-32b}"
browser:
  cloud_provider: browserbase
EOF
fi

if command -v /opt/hermes-venv/bin/hermes >/dev/null 2>&1; then
  HERMES_TUI_TOOLSETS="${HERMES_TUI_TOOLSETS:-browser}" \
    /opt/hermes-venv/bin/hermes dashboard --no-open --host 127.0.0.1 --port 9120 \
    > /tmp/hermes-dashboard.log 2>&1 &
fi

PYTHON_BIN="${PYTHON:-python}"
exec "$PYTHON_BIN" -m uvicorn main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
