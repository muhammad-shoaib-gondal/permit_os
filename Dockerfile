# --- Frontend build ---
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web ./
RUN npm run build

# --- API + agents runtime ---
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY shared ./shared
COPY knowledge ./knowledge
COPY api ./api
COPY agents ./agents
COPY scripts ./scripts
COPY fixtures ./fixtures

RUN pip install --no-cache-dir -e ".[band]"

COPY --from=web /web/dist ./web/dist

RUN mkdir -p /app/data

EXPOSE 8000

ENV DATABASE_URL=sqlite+aiosqlite:///./data/permitos.db

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
