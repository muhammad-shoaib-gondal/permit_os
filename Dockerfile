# API + UI + 4 Band agents — single container (Render default Dockerfile)
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web ./
RUN npm run build

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

RUN pip install --no-cache-dir langchain-openai langgraph anthropic \
    && git clone --depth 1 https://github.com/thenvoi/thenvoi-sdk-python.git /tmp/thenvoi-sdk \
    && pip install --no-cache-dir "/tmp/thenvoi-sdk[langgraph]" \
    && rm -rf /tmp/thenvoi-sdk \
    && pip install --no-cache-dir -e .

COPY --from=web /web/dist ./web/dist

RUN mkdir -p /app/data && chmod +x scripts/start_render_full.sh scripts/ensure_agent_config.sh scripts/agent_supervisor.sh scripts/start_agents_docker.sh

EXPOSE 8000

# Non-secret defaults — match local .env (secrets go in Render Environment)
ENV DATABASE_URL=sqlite+aiosqlite:///./data/permitos.db
ENV PERMITOS_ORCHESTRATION=band
ENV LLM_BACKEND=baseten
ENV OPENAI_API_BASE=https://inference.baseten.co/v1
ENV LLM_MODEL=openai/gpt-oss-120b
ENV LLM_MAX_TOKENS=4096
ENV LLM_MAX_RETRIES=8
ENV SPECIALIST_STAGGER_SEC=90
ENV SPECIALIST_COMPLETE_COOLDOWN_SEC=30
ENV BAND_ORCHESTRATION_TIMEOUT=600
ENV BAND_WS_URL=wss://app.band.ai/api/v1/socket/websocket
ENV BAND_REST_URL=https://app.band.ai
ENV BAND_AGENT_SILENCE_SEC=240
ENV LLM_CROSS_PROCESS_LOCK=1
ENV LLM_MIN_INTERVAL_SEC=4

CMD ["bash", "scripts/start_render_full.sh"]
