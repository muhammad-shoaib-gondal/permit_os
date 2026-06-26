# PermitOS

**The developer's multi-agent permitting team** — coordinates five specialized AI agents through the [Band SDK](https://docs.thenvoi.com) to analyze jurisdiction/zoning, building codes, environmental/utilities, assemble a permit package, and route to human approval with a full audit trail.

**MVP jurisdiction:** Austin, TX  
**Demo project:** Riverside Residences (50-unit multifamily, intentional Block B setback violation)

## Architecture

```
Developer UI → FastAPI → Conductor Agent
                              ↕ Band Chatroom (per case)
         Jurisdiction ←→ Building ←→ Site/Env → Packager → Human
```

| Agent | Role |
|-------|------|
| Conductor | Orchestrator, merge, human gate |
| Jurisdiction & Zoning | Austin LDC, setbacks, FAR |
| Building & Safety | IBC/IRC, fire, ADA |
| Site, Env & Utilities | Flood, stormwater, utilities |
| Permit Packager | Checklist, fees, filing sequence |

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Band account at [band.ai](https://band.ai) — 5 External Agents (for live Band mode)
- LLM API key (OpenAI, Baseten, Groq, etc. — see `.env.example`)

### 2. Backend setup

```bash
cd permit_os
cp .env.example .env
cp agent_config.yaml.example agent_config.yaml
pip install -e ".[dev]"
```

Optional — live Band agents:

```bash
pip install -e ".[band]"
```

### 3. Run API

```bash
uvicorn api.main:app --reload --port 8000
```

```bash
curl http://localhost:8000/health
```

### 4. Frontend (marketing + app)

```bash
cd web
npm install
npm run dev
```

| URL | Page |
|-----|------|
| http://localhost:5173/ | Marketing landing |
| http://localhost:5173/app/ | PermitOS dashboard |

Keep the API running on port 8000 (Vite proxies `/cases`, `/health`, etc.).

Production build (optional — served by FastAPI when `web/dist` exists):

```bash
npm run build
```

### 5. Start Band agents (live mode)

```bash
python -m agents.conductor.agent
python -m agents.jurisdiction.agent
python -m agents.building.agent
python -m agents.site_environmental.agent
python -m agents.packager.agent
```

See [docs/band-agents.md](docs/band-agents.md) for agent registry and credential checks (`python scripts/verify_band_setup.py`).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/disclaimer` | Legal disclaimer |
| POST | `/cases` | Create case + run analysis |
| GET | `/cases/demo/riverside` | Run demo scenario |
| GET | `/cases/{id}` | Get case status + reports |
| POST | `/cases/{id}/approve` | Human approval gate |
| GET | `/cases/{id}/audit` | Audit log entries |
| POST | `/cases/{id}/rfi` | Simulate city RFI + draft response |

## Environment Variables

See `.env.example` for all options. Minimum:

```
OPENAI_API_KEY=         # or another LLM backend (see LLM_BACKEND)
DATABASE_URL=sqlite+aiosqlite:///./permitos.db
```

Band live mode also needs `agent_config.yaml` with 5 agent UUIDs + API keys.

## Tests

```bash
pytest
```

## Disclaimer

PermitOS provides pre-screening assistance only. It does not constitute legal, engineering, or architectural advice.

## License

MIT
