# Deploy PermitOS without keeping your laptop on

Judges need a URL that works 24/7. Pick **Option A** (fastest) or **Option B** (live Band agents in the cloud).

---

## Option A — Single Render service (recommended for judges)

Everything runs **inside the API**. No Band agent processes. No `agent_config.yaml` on the server.

Uses the built-in **local orchestration** (same Austin tools + optional LLM summaries). Set on Render **Environment**:

```env
PERMITOS_ORCHESTRATION=local

LLM_BACKEND=groq
GROQ_API_KEY=your_groq_key
OPENAI_API_BASE=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile

DATABASE_URL=sqlite+aiosqlite:///./data/permitos.db
BAND_ORCHESTRATION_TIMEOUT=600
```

**Why Groq for public demo:** higher rate limits than Baseten (15 req/min). Baseten often stalls mid-analysis.

You do **not** need:
- `agent_config.yaml` Secret File
- A second Render service
- Your laptop on

**Trade-off:** Not a live Band chatroom demo — agents run in-process. Fine for judges testing the product; use Option B for Band showcase.

### Render setup (Option A)

1. **Web Service** → Docker → `./Dockerfile` → branch `feature/multi-llm-band-pipeline`
2. Paste env vars above (use **Add from .env** and change `PERMITOS_ORCHESTRATION=local`)
3. Disk at `/app/data` (optional)
4. Deploy → open URL → upload sample brief → **Analyze**

Analysis usually finishes in **under a minute**.

---

## Option B — Full Band demo in the cloud (2 Render services)

Live agents on Band.ai, both hosted on Render.

### Service 1: API + UI (Web Service)

| Setting | Value |
|---------|--------|
| Dockerfile | `./Dockerfile` |
| Health check | `/health` |

**Environment:**

```env
PERMITOS_ORCHESTRATION=band
BAND_ORCHESTRATION_TIMEOUT=600
BAND_REST_URL=https://app.band.ai
DATABASE_URL=sqlite+aiosqlite:///./data/permitos.db

LLM_BACKEND=groq
GROQ_API_KEY=...
OPENAI_API_BASE=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile

SPECIALIST_STAGGER_SEC=45
SPECIALIST_COMPLETE_COOLDOWN_SEC=30
```

**Secret file:** `agent_config.yaml` → mount at `/app/agent_config.yaml` (full file with all 5 agents).

### Service 2: Band agents (Background Worker)

1. Render → **New +** → **Background Worker**
2. Same repo + branch
3. **Dockerfile path:** `./Dockerfile.agents`
4. **Docker command:** `bash scripts/start_agents_docker.sh` (default in image)
5. **Same Environment** as API (LLM keys + `PERMITOS_ORCHESTRATION=band`)
6. **Same Secret File:** `agent_config.yaml` at `/app/agent_config.yaml`
7. Use **Starter** plan — free tier may sleep workers

This runs jurisdiction, building, site, and packager 24/7 connected to Band.

**No laptop required.**

### Cost note

- 1 Web Service + 1 Background Worker ≈ 2 paid instances on Render Starter (~$14/mo total). Free tier sleeps and breaks long analyses.

---

## Option C — Railway (all-in-one)

1. Import repo on [railway.app](https://railway.app)
2. Service **api**: Dockerfile `./Dockerfile`, public port 8000
3. Services **jurisdiction**, **building**, **site**, **packager**: `Dockerfile.agents` + command `python -m agents.jurisdiction.agent` (one per service)
4. Shared env vars + upload `agent_config.yaml` as variable or file mount

Or use Option A on Railway with one service and `PERMITOS_ORCHESTRATION=local`.

---

## Quick comparison

| | Option A (local) | Option B (Band worker) |
|--|------------------|-------------------------|
| Render services | 1 | 2 |
| Laptop needed | No | No |
| `agent_config.yaml` | No | Yes (both services) |
| Live Band chat | No | Yes |
| Judge reliability | High | Medium (rate limits) |
| Hackathon video | Show Band locally | Can show Band URL |

---

## Recommended for you right now

1. On your **existing Render Web Service**, set `PERMITOS_ORCHESTRATION=local` and switch to **Groq**.
2. Redeploy.
3. Send judges the Render URL — works with your PC off.

Record the hackathon video locally with Band + agents; point submission to the cloud URL for testing.

---

## Smoke test

```bash
curl https://YOUR-APP.onrender.com/health
```

Upload `web/public/sample-project-brief.json` → Analyze → expect full report in ~30–90s (local mode).
