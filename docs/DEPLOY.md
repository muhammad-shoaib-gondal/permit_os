# Deploy EstatePermit

EstatePermit deploys as one web service containing the React application and FastAPI backend.

## Required service

- Build with `Dockerfile`.
- Expose port `8000`.
- Use `/health` as the health-check endpoint.
- Attach persistent storage for uploaded project files and SQLite data.

## Environment

```env
DATABASE_URL=sqlite+aiosqlite:///./data/EstatePermit.db
ZENMUX_API_KEY=your_zenmux_api_key
ZENMUX_BASE_URL=https://zenmux.ai/api/v1
ZENMUX_MODEL=moonshotai/kimi-k3-free
```

`ZENMUX_API_KEY` is mandatory. EstatePermit does not use another LLM provider as a fallback.
Use Postgres and object storage before deploying a multi-tenant production environment.

## Render

1. Create a new Web Service from the repository.
2. Select Docker and `./Dockerfile`.
3. Configure the environment variables above.
4. Add a persistent disk at `/app/data` if using SQLite and local uploads.
5. Deploy and confirm `/health` returns `status: ok` and `product: EstatePermit`.

## Railway

1. Import the repository.
2. Use `./Dockerfile` for the service.
3. Expose port `8000`.
4. Configure the same environment variables.
5. Attach persistent storage or use managed Postgres and object storage.

## Smoke test

Run `python scripts/verify_zenmux_llm.py`, then create a project, upload a relevant file,
and run one permit review. Confirm the case reaches a completed or actionable failed state.
