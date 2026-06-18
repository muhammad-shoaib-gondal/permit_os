# Deploying PermitOS online

PermitOS has three moving parts for a **live Band demo**:

| Component | What it does | Must be public? |
|-----------|----------------|-----------------|
| **API + UI** | Intake, orchestration, results | Yes |
| **4 Band agents** | Jurisdiction, Building, Site, Packager on Band.ai | No (WebSocket to Band) |
| **Secrets** | `agent_config.yaml`, LLM keys, Band conductor key | Never commit |

The API talks to Band over HTTPS; agents only need outbound internet + your secrets.

---

## Recommended: Render (API) + your laptop (agents)

Fastest path for a hackathon video:

1. Deploy **API + built UI** to Render (free tier).
2. Keep **Band agents running** on your machine with `scripts\start_services_background.ps1` (or Docker agents on a small VPS).

Judges open the public URL; agents stay connected to Band in the background.

### 1. Push code

```bash
git push origin feature/multi-llm-band-pipeline
```

Merge to `master` when ready, or deploy from the feature branch.

### 2. Build the UI into the API image

The production `Dockerfile` builds **API + UI only** (no Band SDK). Band agents run on your laptop or via `Dockerfile.agents`.

### 3. Create a Render Web Service

1. [render.com](https://render.com) → **New → Web Service**
2. Connect repo `muhammad-shoaib-gondal/permit_os`
3. Settings:
   - **Branch:** `feature/multi-llm-band-pipeline` (or `master`)
   - **Runtime:** Docker
   - **Dockerfile path:** `./Dockerfile`
   - **Health check path:** `/health`
   - **Plan:** Free or Starter (analysis can run 5–10 minutes — increase timeout if available)

### 4. Environment variables (Render dashboard)

Set these under **Environment** (never commit real values):

```env
PERMITOS_ORCHESTRATION=band
BAND_ORCHESTRATION_TIMEOUT=600
DATABASE_URL=sqlite+aiosqlite:///./data/permitos.db

LLM_BACKEND=baseten
BASETEN_API_KEY=...
OPENAI_API_BASE=https://inference.baseten.co/v1
LLM_MODEL=openai/gpt-oss-120b
LLM_MAX_TOKENS=4096
LLM_MAX_RETRIES=8
SPECIALIST_STAGGER_SEC=90
SPECIALIST_COMPLETE_COOLDOWN_SEC=30
```

**Conductor / Band REST** — paste from `agent_config.yaml`:

```env
BAND_REST_URL=https://app.band.ai
# Conductor agent API key (orchestrator uses this to post messages)
PERMITOS_CONDUCTOR_API_KEY=...
```

Check `shared/band_client/config.py` for exact env names your build expects; mirror whatever is in your local `agent_config.yaml`.

### 5. Persistent disk (optional)

Add a Render disk mounted at `/app/data` so SQLite survives redeploys.

### 6. Start agents locally (before recording)

```powershell
cd C:\Users\HP\projects\permitos
.\scripts\start_services_background.ps1   # or agents only if API is on Render
```

Confirm logs: `logs\agents-jurisdiction-agent.err.log` shows `Agent started`.

### 7. Smoke test

```bash
curl https://YOUR-APP.onrender.com/health
```

Open the URL → upload `web/public/sample-project-brief.json` → **Analyze**.

---

## Alternative: Railway (API + agents)

Railway can run multiple services from `docker-compose.yml`:

1. **Service 1:** `api` (public port 8000)
2. **Services 2–5:** `jurisdiction`, `building`, `site`, `packager` with `profiles: agents` commands

Upload `agent_config.yaml` as a secret file or env vars per agent UUID.

---

## Alternative: Single VPS (Docker Compose)

```bash
docker compose up -d api
docker compose --profile agents up -d
```

Put Caddy or nginx in front with HTTPS. Build UI first or use the multi-stage Dockerfile.

---

## What not to deploy in git

- `.env`
- `agent_config.yaml`
- API keys in chat / README

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Analyze spins forever | Agents not running or wrong Band keys |
| Stops after jurisdiction | LLM rate limit (Baseten 15/min) — wait 5 min, one run at a time |
| 502 on Render | Free tier sleep — wake with `/health`, retry |
| CORS errors | UI should be served from same host as API (production Dockerfile does this) |
