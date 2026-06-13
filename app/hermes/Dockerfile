FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=9120 \
    HOST=0.0.0.0 \
    HERMES_HOME=/data/.hermes \
    HERMES_TUI_TOOLSETS=browser

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "hermes-agent[web]" \
    && npm install -g agent-browser \
    && agent-browser install --with-deps

COPY start.sh ./
RUN chmod +x ./start.sh

EXPOSE 9120

CMD ["./start.sh"]
