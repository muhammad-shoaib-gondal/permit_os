# --- Frontend build ---
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web ./
RUN npm run build

# --- API runtime ---
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY shared ./shared
COPY knowledge ./knowledge
COPY api ./api
COPY fixtures ./fixtures

# Band REST client for orchestrator (clone without git submodules — Render-safe)
RUN pip install --no-cache-dir -e . \
    && git clone --depth 1 https://github.com/thenvoi/thenvoi-sdk-python.git /tmp/thenvoi-sdk \
    && pip install --no-cache-dir /tmp/thenvoi-sdk \
    && rm -rf /tmp/thenvoi-sdk

COPY --from=web /web/dist ./web/dist

RUN mkdir -p /app/data

EXPOSE 8000

ENV DATABASE_URL=sqlite+aiosqlite:///./data/permitos.db
ENV PERMITOS_ORCHESTRATION=local
ENV LOCAL_SKIP_LLM=1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
