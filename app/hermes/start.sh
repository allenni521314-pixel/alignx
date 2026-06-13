#!/usr/bin/env sh
set -eu

export HERMES_HOME="${HERMES_HOME:-/data/.hermes}"
mkdir -p "$HERMES_HOME"

HERMES_AI_API_MODE="${HERMES_AI_API_MODE:-chat_completions}"
HERMES_MODEL_PROVIDER="${HERMES_MODEL_PROVIDER:-}"
HERMES_MODEL_NAME="${HERMES_MODEL_NAME:-}"
HERMES_MODEL_BASE_URL="${HERMES_MODEL_BASE_URL:-}"
HERMES_MODEL_API_KEY="${HERMES_MODEL_API_KEY:-}"

if [ -z "$HERMES_MODEL_API_KEY" ] && [ -n "${OPENAI_API_KEY:-}" ]; then
  HERMES_MODEL_API_KEY="$OPENAI_API_KEY"
  HERMES_MODEL_PROVIDER="${HERMES_MODEL_PROVIDER:-custom}"
  HERMES_MODEL_BASE_URL="${HERMES_MODEL_BASE_URL:-${OPENAI_BASE_URL:-https://api.openai.com/v1}}"
  HERMES_MODEL_NAME="${HERMES_MODEL_NAME:-${AI_DEFAULT_MODEL:-gpt-4.1-mini}}"
elif [ -z "$HERMES_MODEL_API_KEY" ] && [ -n "${DEEPSEEK_API_KEY:-}" ]; then
  HERMES_MODEL_API_KEY="$DEEPSEEK_API_KEY"
  HERMES_MODEL_PROVIDER="${HERMES_MODEL_PROVIDER:-deepseek}"
  HERMES_MODEL_NAME="${HERMES_MODEL_NAME:-deepseek-v4-pro}"
elif [ -z "$HERMES_MODEL_API_KEY" ] && [ -n "${DASHSCOPE_API_KEY:-${QWEN_API_KEY:-${VISION_API_KEY:-}}}" ]; then
  HERMES_MODEL_API_KEY="${DASHSCOPE_API_KEY:-${QWEN_API_KEY:-${VISION_API_KEY:-}}}"
  HERMES_MODEL_PROVIDER="${HERMES_MODEL_PROVIDER:-custom}"
  HERMES_MODEL_BASE_URL="${HERMES_MODEL_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
  HERMES_MODEL_NAME="${HERMES_MODEL_NAME:-qwen3-32b}"
fi

HERMES_MODEL_PROVIDER="${HERMES_MODEL_PROVIDER:-deepseek}"
HERMES_MODEL_NAME="${HERMES_MODEL_NAME:-deepseek-v4-pro}"

if [ "$HERMES_MODEL_PROVIDER" = "deepseek" ] && [ -n "$HERMES_MODEL_API_KEY" ] && [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  export DEEPSEEK_API_KEY="$HERMES_MODEL_API_KEY"
fi

has_nous_gateway_auth() {
  if [ -n "${TOOL_GATEWAY_USER_TOKEN:-}" ]; then
    return 0
  fi
  if [ -f "$HERMES_HOME/auth.json" ] && grep -q '"nous"' "$HERMES_HOME/auth.json"; then
    return 0
  fi
  return 1
}

write_runtime_config() {
  {
    echo "toolsets:"
    echo "  - browser"
    echo "browser:"
    if [ -n "${BROWSERBASE_API_KEY:-}" ] && [ -n "${BROWSERBASE_PROJECT_ID:-}" ]; then
      echo "  cloud_provider: browserbase"
    elif has_nous_gateway_auth; then
      echo "  cloud_provider: browser-use"
    fi
    echo "  auto_local_for_private_urls: false"
    echo "  command_timeout: 120"
    echo "  inactivity_timeout: 240"
    if [ -z "${BROWSERBASE_API_KEY:-}" ] || [ -z "${BROWSERBASE_PROJECT_ID:-}" ]; then
      if has_nous_gateway_auth; then
        echo "tool_gateway:"
        echo "  browser: gateway"
      fi
    fi
    echo "agent:"
    echo "  max_turns: 80"
  } >> "$HERMES_HOME/config.yaml"
}

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
EOF
    write_runtime_config
  else
    cat > "$HERMES_HOME/config.yaml" <<EOF
model:
  provider: "${HERMES_MODEL_PROVIDER}"
  base_url: "${HERMES_MODEL_BASE_URL}"
  default: "${HERMES_MODEL_NAME}"
  api_key: "${HERMES_MODEL_API_KEY:-}"
EOF
    write_runtime_config
  fi
fi

exec hermes dashboard --no-open --host "${HOST:-0.0.0.0}" --port "${PORT:-9120}" --insecure
