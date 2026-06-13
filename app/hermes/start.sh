#!/usr/bin/env sh
set -eu

export HERMES_HOME="${HERMES_HOME:-/data/.hermes}"
mkdir -p "$HERMES_HOME"

HERMES_MODEL_PROVIDER="${HERMES_MODEL_PROVIDER:-deepseek}"
HERMES_MODEL_NAME="${HERMES_MODEL_NAME:-deepseek-v4-pro}"
HERMES_MODEL_BASE_URL="${HERMES_MODEL_BASE_URL:-}"
HERMES_MODEL_API_KEY="${HERMES_MODEL_API_KEY:-${DEEPSEEK_API_KEY:-${OPENAI_API_KEY:-${DASHSCOPE_API_KEY:-${QWEN_API_KEY:-${APP_AI_KEY:-}}}}}}"
HERMES_AI_API_MODE="${HERMES_AI_API_MODE:-chat_completions}"

if [ "${HERMES_MANAGED_CONFIG:-true}" != "false" ]; then
  if [ "$HERMES_MODEL_PROVIDER" = "custom" ]; then
    cat > "$HERMES_HOME/config.yaml" <<EOF
model:
  provider: custom
  base_url: "${HERMES_MODEL_BASE_URL}"
  default: "${HERMES_MODEL_NAME}"
  api_key: "${HERMES_MODEL_API_KEY:-}"
  api_mode: "${HERMES_AI_API_MODE}"
custom_providers:
  - name: alignx-hermes
    base_url: "${HERMES_MODEL_BASE_URL}"
    api_key: "${HERMES_MODEL_API_KEY:-}"
    api_mode: "${HERMES_AI_API_MODE}"
    model: "${HERMES_MODEL_NAME}"
browser:
  cloud_provider: browserbase
  auto_local_for_private_urls: false
agent:
  max_turns: 80
EOF
  else
    cat > "$HERMES_HOME/config.yaml" <<EOF
model:
  provider: "${HERMES_MODEL_PROVIDER}"
  base_url: "${HERMES_MODEL_BASE_URL}"
  default: "${HERMES_MODEL_NAME}"
browser:
  cloud_provider: browserbase
  auto_local_for_private_urls: false
agent:
  max_turns: 80
EOF
  fi
fi

exec hermes dashboard --no-open --host "${HOST:-0.0.0.0}" --port "${PORT:-9120}" --insecure
