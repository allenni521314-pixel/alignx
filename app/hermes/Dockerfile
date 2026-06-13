FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=9120 \
    HOST=0.0.0.0 \
    HERMES_HOME=/data/.hermes \
    HERMES_TUI_TOOLSETS=browser \
    AGENT_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium \
    AGENT_BROWSER_ARGS=--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--disable-extensions,--disable-background-networking,--disable-background-timer-throttling,--disable-renderer-backgrounding,--blink-settings=imagesEnabled=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl nodejs npm chromium \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "hermes-agent[web]" \
    && npm install -g agent-browser

COPY start.sh ./
RUN chmod +x ./start.sh

EXPOSE 9120

CMD ["./start.sh"]
