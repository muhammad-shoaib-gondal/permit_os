# --- Frontend build ---
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web ./
RUN npm run build

# --- API runtime (no Band SDK — orchestrator uses httpx only) ---
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shared ./shared
COPY knowledge ./knowledge
COPY api ./api
COPY fixtures ./fixtures

RUN pip install --no-cache-dir -e .

COPY --from=web /web/dist ./web/dist

RUN mkdir -p /app/data

EXPOSE 8000

ENV DATABASE_URL=sqlite+aiosqlite:///./data/permitos.db
ENV PERMITOS_ORCHESTRATION=local
ENV LOCAL_SKIP_LLM=1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
