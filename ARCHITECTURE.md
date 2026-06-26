# PermitOS — Architecture & Project Plan

> Share this file with any LLM and it will have full context about what the project does, how it works, and how to extend it.

---

## 1. What PermitOS Does

Real estate developers waste weeks chasing city agencies before they even know if their project is permittable. A developer in Austin can spend 2–6 weeks doing manual research across zoning codes, building codes, environmental regulations, and fee schedules — only to discover a fatal setback violation on day 45.

**PermitOS solves this.** It is an AI-powered permit pre-screening platform for real estate development. Given a project brief (address, unit count, stories, square footage, parking), it runs an automated analysis across four permit domains and returns within minutes:

- Which permits are required and from which agencies
- Whether the design passes zoning, building code, and environmental checks
- An executive summary written by an LLM from the structured findings
- A permit package with fee estimates, filing sequence, and required documents
- An immutable audit hash of the full package

The primary user is a **real estate developer or their permitting consultant**. The secondary user is a **city planner or permit analyst** reviewing submissions.

---

## 2. How It Works — Technical Architecture

### 2.1 System Overview

```
Browser (React SPA)
    │
    │  HTTP / SSE  (poll /cases/{id} every 3s)
    ▼
FastAPI backend  (api/)
    │
    ├── POST /cases/analyze    → parse upload, create DB row, run pipeline in background
    ├── GET  /cases/{id}       → poll status + partial results
    ├── POST /cases/{id}/approve
    └── POST /cases/{id}/rfi
    │
    ▼
LLM Pipeline  (shared/agent_logic/local_runner.py)
    │
    ├── Step 1: Jurisdiction   (deterministic)  →  JurisdictionReport
    ├── Step 2: Building       (deterministic)  →  BuildingSafetyReport
    ├── Step 3: Site/Env       (deterministic)  →  SiteEnvironmentalReport
    ├── Step 4: LLM call       (1x Baseten API) →  executive_summary (string)
    └── Step 5: Package        (deterministic)  →  PermitPackage
    │
    ▼
SQLite database  (permitos.db)
    ├── permit_cases    — one row per case, JSON results blob
    └── audit_log       — immutable event stream per case
```

### 2.2 Key Directories

```
permit_os/
├── api/
│   ├── main.py             FastAPI app, static file serving, route registration
│   ├── routes/cases.py     REST endpoints for case lifecycle
│   ├── services/
│   │   ├── case_service.py DB reads/writes, background task dispatch
│   │   └── intake.py       Project brief file parser (.json / .zip)
│   └── models.py           SQLAlchemy ORM models
│
├── shared/
│   ├── config.py           AgentRole enum, Settings (database URL, port)
│   ├── agent_logic/
│   │   └── local_runner.py MAIN PIPELINE — see section 2.4
│   ├── llm/
│   │   └── backends.py     LLM backend config (Baseten, Groq, Ollama, etc.)
│   ├── tools/
│   │   ├── workflow.py     Thin entry point → local_runner
│   │   ├── conductor.py    compute_readiness(), detect_conflicts(), merge_reports()
│   │   ├── jurisdiction_tools.py  Pure-Python lookup functions
│   │   ├── building_tools.py      Pure-Python code checks
│   │   ├── site_tools.py          Flood zone / utility lookups
│   │   └── knowledge.py    JSON knowledge-base loader (cached)
│   └── schemas/
│       ├── project_brief.py   Input schema (ProjectBrief, BlockSetback)
│       ├── reports.py         JurisdictionReport, BuildingSafetyReport, SiteEnvironmentalReport
│       ├── package.py         PermitPackage, PermitRequirement, DocumentRequirement
│       └── case.py            PermitCaseSummary, CaseStatus, ReadinessScore
│
├── knowledge/austin/       JSON knowledge base for Austin, TX
│   ├── zoning_rules.json
│   ├── building_code_snippets/snippets.json
│   ├── environmental_triggers.json
│   ├── fee_schedule.json
│   └── permit_catalog.json
│
└── web/                    React + Vite frontend
    ├── index.html          Marketing landing page (served at /)
    ├── app/index.html      React SPA entry (served at /app/)
    └── src/
        ├── App.tsx         Dashboard (auth gate + tabbed results UI)
        ├── LoginPage.tsx   Fixed-credential login (admin/admin)
        ├── SignupPage.tsx  Placeholder signup
        ├── auth.ts         sessionStorage-based auth helpers
        └── api.ts          Frontend API client (fetch + polling)
```

### 2.3 Data Flow — Step by Step

1. **User uploads** a `.json` project brief (or uses the demo) via the React dashboard.
2. **Frontend** POSTs to `POST /cases/analyze` (multipart form with file + metadata).
3. **`intake.py`** parses the JSON into a `ProjectBrief` Pydantic model.
4. **`case_service.py`** creates a `PermitCase` DB row with `status=ANALYZING` and immediately returns `case_id` to the frontend. The actual pipeline runs in a background asyncio task.
5. **Frontend polls** `GET /cases/{case_id}` every 3 seconds. Partial results are returned as they arrive.
6. **Pipeline** (`local_runner.py`) runs the four analysis steps, writing progress to the DB between each step.
7. When done, the case row is updated to `status=AWAITING_APPROVAL` with the full JSON results blob.
8. **User reviews** the results, clicks "Approve for Filing" → `POST /cases/{id}/approve` sets status to `APPROVED_FOR_FILING` and records the audit hash.

### 2.4 The LLM Pipeline (local_runner.py)

The pipeline makes exactly **one LLM API call** per case analysis. Everything else is deterministic.

| Step | What happens | LLM? |
|------|-------------|-------|
| Jurisdiction | `lookup_jurisdiction()` → `get_zoning_rules()` → `calculate_setbacks()` | No |
| Building | `check_egress()` → `check_sprinklers()` → `check_accessibility()` | No |
| Site | `lookup_flood_zone()` → `get_utility_requirements()` | No |
| **LLM call** | All findings → Baseten API → executive summary string (2-3 sentences) | **Yes (1x)** |
| Package | `permit_catalog.json` + fee schedule → PermitPackage | No |

The LLM receives a structured JSON of all findings and writes a plain-English executive summary. If the LLM call fails (timeout, rate limit, API error), a deterministic fallback string is used — **the pipeline never fails because of the LLM**.

#### LLM Configuration

Controlled by environment variables in `.env`:

```env
LLM_BACKEND=baseten
BASETEN_API_KEY=your_key
LLM_MODEL=openai/gpt-oss-120b
LLM_MAX_TOKENS=1024
```

Set `LOCAL_SKIP_LLM=1` to disable the LLM call entirely (useful for testing).

### 2.5 Authentication

Simple session-based auth in the frontend only (no backend auth middleware):

- Hard-coded credentials: `admin` / `admin`
- State stored in `sessionStorage` (cleared when browser tab closes)
- All `/app/*` routes render the React SPA; the SPA checks `isAuthenticated()` before showing the dashboard
- If not authenticated, the login page is rendered instead (no redirect, same entry point)

---

## 3. What Problem We're Solving — What a "Normal Plan" Looks Like

### 3.1 The Real Estate Permitting Problem

A typical development project requires permits from multiple agencies before breaking ground. For a 50-unit multifamily building in Austin, a developer needs to navigate:

**Typical permit application components:**

| Component | Description | Common issues |
|-----------|-------------|---------------|
| Site plan | Dimensioned drawing showing lot lines, setbacks, parking, utilities | Setback violations are the #1 rejection cause |
| Architectural drawings | Floor plans, elevations, sections | Egress path compliance (IBC), accessibility (ADA) |
| Zoning compliance letter | Written confirmation of use & density | MF-3 zoning requires specific density limits |
| Fire apparatus access plan | Showing fire truck turning radii and hydrant locations | Required for buildings >4 stories |
| Stormwater management plan | Impervious surface calculations, drainage design | Required if >0.5 acres impervious |
| Environmental clearances | Flood zone certification (FEMA), tree survey | Zone A/AE flood → expensive mitigation |
| Utility availability letters | Water/sewer capacity confirmation | Can delay 3-6 months for large units |

**Typical permit types required (Austin, TX):**

1. **Building Permit** (COA) — primary permit for structure
2. **Site Plan Permit** (COA Land Use Review) — required for >4 units
3. **Electrical Permit** (COA) — separate from building
4. **Mechanical Permit** (COA) — HVAC, gas
5. **Plumbing Permit** (COA) — water/sewer connections
6. **Fire Suppression Permit** (AFD) — sprinkler systems

**Typical timeline without pre-screening:**
- Week 1-3: Developer commissions architectural drawings
- Week 3-6: Architect discovers zoning issues, redesigns
- Week 6-8: Resubmit to city, wait for initial review
- Week 8-12: City issues Request for Information (RFI), developer responds
- Week 12-16: Permit approval (best case)

**With PermitOS:** developer discovers the setback violation on day 1, before any drawings are commissioned. The estimated savings: **4-8 weeks and $50k-200k** in redesign costs.

---

## 4. Improving the Plan Evaluation Mechanism

### 4.1 Current Approach

The current pipeline is **rule-based + one LLM call**:

- Deterministic tools query JSON knowledge bases (locally stored Austin codes)
- Results are assembled into structured Pydantic models
- One LLM call produces a plain-English executive summary

**Strengths:** Fast (< 5s on first run, tools are `@lru_cache`d), predictable, cheap (one LLM call), easy to test, zero external dependencies at runtime.

**Weaknesses:** The knowledge base is static JSON — it doesn't know about recent code amendments, special overlay districts, or case law.

### 4.2 Do We Need a Multi-Agent Architecture?

**Short answer: Not yet.** Here's the analysis:

| Approach | Pros | Cons | Recommended for |
|----------|------|------|-----------------|
| **Current: Tools + 1 LLM** | Fast, cheap, testable | Static knowledge, no reasoning | MVP, demo, single city |
| **Multi-step LLM chain** | Richer analysis, catches edge cases | 3-5x more expensive, slower | Production with complex projects |
| **Multi-agent (Band/LangGraph)** | Parallel analysis, agent specialization | Complex, expensive, hard to debug | Multi-jurisdiction at scale |
| **RAG over live codes** | Up-to-date, authoritative | Infrastructure complexity | Enterprise product |

**Recommended next step:** Replace the static JSON knowledge bases with a multi-step LLM reasoning chain:

```
Step 1: LLM reads project brief + zoning code text → structured analysis
Step 2: LLM reads building code snippets + brief → structured checks
Step 3: LLM combines all findings → executive summary + conflict detection
```

This uses 3 LLM calls per case (vs 1 currently) but produces significantly richer analysis — particularly for edge cases like mixed-use zoning, overlay districts, and non-standard project types.

### 4.3 Improved Conflict Detection

Currently `detect_conflicts()` in `conductor.py` is hardcoded. An improved version would:

1. **Ask the LLM to cross-reference** jurisdiction report with building report (e.g., sprinkler requirement affects setback clearance for fire trucks)
2. **Generate remediation paths** with specific code citations (variance application process, by-right alternatives)
3. **Estimate impact on timeline** based on conflict type (administrative variance = +30 days, design change = +60 days)

---

## 5. Adding More Cities — Data Storage Strategy

### 5.1 Current State

The system is Austin-only. All knowledge is in `knowledge/austin/` as static JSON files authored manually.

### 5.2 Strategy for Multiple Cities

#### Option A: Static JSON per City (Current + Scale)

Extend the current pattern: `knowledge/{city_slug}/` directory per city.

```
knowledge/
├── austin_tx/
├── houston_tx/
├── dallas_tx/
└── phoenix_az/
```

**Best for:** 2-10 cities, manually curated, high accuracy needed.

**How to add a new city:**
1. Create `knowledge/{city}/zoning_rules.json` — zoning districts, permitted uses, setbacks
2. Create `knowledge/{city}/building_code_snippets/snippets.json` — IBC local amendments
3. Create `knowledge/{city}/environmental_triggers.json` — flood zones, stormwater thresholds
4. Create `knowledge/{city}/fee_schedule.json` — permit fees, formula
5. Create `knowledge/{city}/permit_catalog.json` — permit types, agencies, timeline estimates
6. Update `jurisdiction_tools.lookup_jurisdiction()` to route the city to its knowledge base
7. Update the frontend `JURISDICTIONS` list in `api.ts`

**Effort per city:** 2-3 days of research + data entry.

#### Option B: RAG over Official Code Documents (Recommended for Scale)

For 10+ cities or for keeping codes up to date, use **Retrieval-Augmented Generation**:

```
Architecture:
  ┌─────────────────────────────────────────────────────┐
  │  Ingestion pipeline (offline, scheduled weekly)       │
  │  ┌─────────┐   chunk + embed   ┌──────────────────┐  │
  │  │ PDF/HTML │ ─────────────→   │ Vector DB        │  │
  │  │ city code│                  │ (Pinecone/Chroma) │  │
  │  └─────────┘                   └──────────────────┘  │
  └─────────────────────────────────────────────────────┘
                                          │
  ┌─────────────────────────────────────────────────────┐
  │  Query time (per case)                               │
  │  project brief → embed query → retrieve top-K chunks │
  │  → LLM reads chunks + brief → structured analysis    │
  └─────────────────────────────────────────────────────┘
```

**Implementation steps:**

1. **Ingestion**: Scrape or download official code PDFs (e.g., Austin Land Development Code, IBC), chunk into 512-token segments, embed with OpenAI `text-embedding-3-small`, store in a vector database (Chroma for local dev, Pinecone for production).

2. **Retrieval**: At analysis time, query the vector DB with `"setback requirements MF-3 Austin residential"` etc. to retrieve the most relevant code sections.

3. **LLM reasoning**: Feed retrieved chunks + project brief to the LLM in a single structured prompt. The LLM applies the retrieved code to the specific project.

**Recommended vector DB:** Start with **ChromaDB** (embeds in the FastAPI process, zero infra), migrate to **Pinecone** when handling 50+ cities.

**Cost model:** ~$0.002 per case for embeddings + ~$0.05 per case for LLM reasoning = $0.052 per analysis. At 1000 cases/month = $52/month.

#### Option C: Live Code API Integration

Some jurisdictions expose machine-readable APIs:
- Austin: [developer.austintexas.gov](https://developer.austintexas.gov) (permit status, GIS)
- OpenGovUS: aggregated permit data

This is the eventual target for a production system but requires significant integration work per city.

### 5.3 Recommended Rollout Path

| Phase | Cities | Approach | Effort |
|-------|--------|----------|--------|
| MVP (now) | Austin, TX | Static JSON | Done |
| Phase 2 | + 3-5 Texas cities | Static JSON per city | 1 week |
| Phase 3 | + 10-20 cities | RAG over code PDFs (Chroma) | 2-3 weeks |
| Phase 4 | 50+ cities | RAG + Pinecone + live APIs | 1-2 months |

---

## 6. Running the Project Locally

### Backend

```bash
cd permit_os
pip install -e ".[dev]"
cp .env.example .env   # add your BASETEN_API_KEY
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd permit_os/web
npm install
npm run dev    # → http://localhost:5173
```

URLs:
- Marketing page: `http://localhost:5173/`
- Dashboard (login required): `http://localhost:5173/app/`
- Login: `admin` / `admin`

### Environment Variables (key ones)

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_BACKEND` | Which LLM provider | `baseten` |
| `BASETEN_API_KEY` | Baseten API key | — |
| `LLM_MODEL` | Model name | `openai/gpt-oss-120b` |
| `LLM_MAX_TOKENS` | Max tokens per LLM call | `1024` |
| `LOCAL_SKIP_LLM` | Skip LLM, use fallback summary | `0` |
| `DATABASE_URL` | SQLAlchemy DB URL | `sqlite+aiosqlite:///./permitos.db` |

### Tests

```bash
cd permit_os
LOCAL_SKIP_LLM=1 python -m pytest tests/ -q
```

---

## 7. Team

- Muhammad Shoaib
- Sibtain Ahmed
- Azeem Kamran
- Hasnain Ahmed
