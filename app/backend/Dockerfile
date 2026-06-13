FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    DATABASE_URL=sqlite+aiosqlite:////data/sql_app.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m venv /opt/hermes-venv \
    && /opt/hermes-venv/bin/pip install --no-cache-dir "hermes-agent[web]" \
    && npm install -g agent-browser

COPY . .
RUN chmod +x ./start.sh

EXPOSE 8000

CMD ["./start.sh"]
