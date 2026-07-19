# EstatePermit API and UI.
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

COPY pyproject.toml ./
COPY shared ./shared
COPY knowledge ./knowledge
COPY api ./api
COPY scripts ./scripts
COPY fixtures ./fixtures

RUN pip install --no-cache-dir -e .

COPY --from=web /web/dist ./web/dist

RUN mkdir -p /app/data && chmod +x scripts/start_render_full.sh

EXPOSE 8000

ENV DATABASE_URL=sqlite+aiosqlite:///./data/EstatePermit.db
ENV ZENMUX_BASE_URL=https://zenmux.ai/api/v1
ENV ZENMUX_MODEL=moonshotai/kimi-k3-free
ENV ZENMUX_MAX_TOKENS=8192
ENV ZENMUX_MAX_RETRIES=4
ENV ZENMUX_TIMEOUT_SEC=180

CMD ["bash", "scripts/start_render_full.sh"]
