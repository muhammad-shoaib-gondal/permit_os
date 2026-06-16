# PermitOS

**The developer's multi-agent permitting team** — Band of Agents Hackathon, Track 3: Regulated & High-Stakes Workflows.

PermitOS coordinates five specialized AI agents through the [Band SDK](https://docs.thenvoi.com) to analyze jurisdiction/zoning, building codes, environmental/utilities, assemble a permit package, and route to human approval with a full audit trail.

**MVP jurisdiction:** Austin, TX  
**Demo project:** Riverside Residences (50-unit multifamily, intentional Block B setback violation)

## Architecture

```
Developer UI → FastAPI → Conductor Agent
                              ↕ Band Chatroom (per case)
         Jurisdiction ←→ Building ←→ Site/Env → Packager → Human
```

| Agent | Role | Framework | Model provider |
|-------|------|-----------|----------------|
| Conductor | Orchestrator, merge, human gate | LangGraph | AI/ML API |
| Jurisdiction & Zoning | Austin LDC, setbacks, FAR | Anthropic/CrewAI | Featherless (OSS) |
| Building & Safety | IBC/IRC, fire, ADA | LangGraph | AI/ML API |
| Site, Env & Utilities | Flood, stormwater, utilities | PydanticAI | Featherless (OSS) |
| Permit Packager | Checklist, fees, filing sequence | Anthropic | AI/ML API |

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Band account at [band.ai](https://band.ai) — create **5 External Agents** (for live Band mode)
- AI/ML API + Featherless keys (partner prizes)

### 2. Backend setup

```bash
cd permitos
cp .env.example .env
cp agent_config.yaml.example agent_config.yaml
pip install -e ".[dev]"
```

Optional — live Band agents:

```bash
pip install -e ".[band]"   # may require git SSH access for thenvoi SDK
```

### 3. Run API + demo pipeline

```bash
uvicorn api.main:app --reload --port 8000
```

```bash
curl http://localhost:8000/cases/demo/riverside
```

### 4. Frontend

```bash
cd web
npm install
npm run dev          # http://localhost:5173 (proxies API)
# or build for production:
npm run build        # served at http://localhost:8000/ when dist exists
```

Click **Run Riverside Residences Demo** to see:
- Live agent activity feed (Band-style events)
- Compliance report with pass/fail/warn + citations
- Conductor conflict + suggested fix
- Permit package ($47,200, 45-day estimate)
- Human approve → audit hash
- Simulate City RFI → Packager draft

### 5. Start Band agents (when credentials configured)

```bash
python -m agents.conductor.agent
python -m agents.jurisdiction.agent
python -m agents.building.agent
python -m agents.site_environmental.agent
python -m agents.packager.agent
```

Or Docker:

```bash
docker compose up api
docker compose --profile agents up   # all 5 agents + API
```

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

## Build Status

- [x] Phase 1 — Schemas, Band client, Docker skeleton
- [x] Phase 2 (partial) — Austin knowledge pack + deterministic tools
- [x] Phase 6 (partial) — FastAPI, SQLite, audit log
- [x] Phase 7 (partial) — React dashboard, demo flow, approve, RFI
- [ ] Phase 3–5 — Live Band @mention orchestration (requires Band credentials)
- [ ] Phase 8 — End-to-end Band hardening + video

See [docs/PermitOS-Technical-Strategy.md](docs/PermitOS-Technical-Strategy.md) for prize alignment and [docs/PermitOS-Project-Document.md](docs/PermitOS-Project-Document.md) for full spec.

## Environment Variables

```
AIML_API_KEY=          # AI/ML API partner prize
FEATHERLESS_API_KEY=   # Featherless partner prize
OPENAI_API_KEY=        # Fallback / Band adapters
DATABASE_URL=sqlite+aiosqlite:///./permitos.db
```

Band agents also need `agent_config.yaml` with 5 agent UUIDs + API keys.

## Disclaimer

PermitOS provides pre-screening assistance only. It does not constitute legal, engineering, or architectural advice.

## License

MIT
