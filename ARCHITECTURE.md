# PermitOS — Architecture & Project Plan

> Share this file with any LLM and it will have full context about what the product does, how it works today, what is missing, and where to focus next.

**Last updated:** July 2026 (post project-workspace + multi-jurisdiction UI)

---

## 1. What PermitOS Does

Real estate developers waste weeks chasing city agencies before they know if a project is even permittable. Manual research across zoning, building code, environmental triggers, and fee schedules often surfaces a fatal issue weeks into design.

**PermitOS** is an AI-assisted permit **pre-screening** platform. A developer creates a project, uploads a structured brief (and supporting docs), picks analysis modules, and gets:

- Pass / fail / warn checks with code citations (zoning, building, fire/site)
- Conflict detection across domains
- A permit package (required permits, fee estimate, filing sequence, document list)
- Optional LLM-polished executive summary language
- Human approval gate + SHA-256 audit hash of the package
- Client-side PDF export of the report

**Primary user:** real estate developer or permitting consultant  
**Secondary user (aspirational):** city planner / reviewer — not built yet

**Honest product boundary:** PermitOS prepares a stronger submittal package. It does **not** e-file with the city, parse CAD geometry, or replace a PE/architect stamp.

---

## 2. How It Works Today — Technical Architecture

### 2.1 System Overview

The **primary user path** is the project workspace (not the legacy one-shot `/cases` demo):

```
Browser (React SPA at /app)
    │
    │  Project CRUD, file uploads, rules, analyze, poll
    ▼
FastAPI  (api/)
    │
    ├── /projects/*          → create project, files, rules, kick analysis
    ├── /cases/{id}          → poll status + partial results
    ├── /cases/{id}/approve  → human gate + audit hash
    ├── /cases/{id}/rfi      → simulated RFI draft (template)
    └── /jurisdictions       → list knowledge packs
    │
    ▼
Orchestration switch  (shared/tools/workflow.py)
    │
    ├── local  → local_runner.py   (default / reliable path)
    └── band   → Band chatroom + 5 agent processes (optional, fragile)
    │
    ▼
Deterministic tools + knowledge JSON
    ├── jurisdiction_tools / building_tools / site_tools
    ├── conductor.merge_reports / detect_conflicts / readiness
    ├── custom_rules.py (LLM eval of user rules, WARN fallback)
    └── optional 1-line LLM polish per report section
    │
    ▼
SQLite  (permitos.db)
    ├── projects, project_files
    ├── permit_cases  (results JSON blob + status)
    └── audit_log
```

**Orchestration selection** (`workflow.py`):

| Condition | Mode |
|-----------|------|
| `PERMITOS_VIDEO_MODE=1` | always `local` (fast demo, no Band/LLM) |
| `PERMITOS_ORCHESTRATION=local\|band` | that mode |
| else if Band credentials present | `band` |
| else | `local` |

If Band is auto-selected but credentials are missing, the system **falls back to local**. Only an explicit `PERMITOS_ORCHESTRATION=band` raises when Band is unavailable.

### 2.2 Key Directories

```
permit_os/
├── api/
│   ├── main.py                 FastAPI app, serves web/dist + /app SPA
│   ├── models.py               Project, ProjectFile, PermitCase, AuditLogEntry
│   ├── routes/
│   │   ├── projects.py         PRIMARY API surface (CRUD, files, rules, analyze)
│   │   ├── cases.py            Case poll / approve / legacy demo + analyze
│   │   ├── jurisdictions.py    List knowledge packs
│   │   └── audit.py            Audit log + RFI simulate
│   └── services/
│       ├── project_service.py  Projects, file gating, Manhattan rule library
│       ├── case_service.py     Background analysis tasks, approve, RFI
│       ├── intake.py           Project brief parser (.json / .zip)
│       ├── db_migrate.py       Ad-hoc SQLite migrations on startup
│       └── permit_review_service.py  DEAD CODE (tests only)
│
├── shared/
│   ├── agent_logic/
│   │   ├── local_runner.py     MAIN reliable pipeline
│   │   └── custom_rules.py     LLM eval of per-project custom rules
│   ├── band_client/            Band REST orchestrator + agent factory
│   ├── llm/backends.py         OpenAI-compatible adapters (10 providers)
│   ├── tools/                  Deterministic checks + knowledge loader
│   └── schemas/                Pydantic models for brief/reports/package/case
│
├── agents/*/agent.py           Thin Band agent entrypoints (all LangGraph today)
│
├── knowledge/
│   ├── austin/                 Fully wired into scoring tools (active)
│   ├── kansas/manhattan/       Rich pack + 266 code chunks (rules UI > pipeline)
│   └── washington/seattle/     Pack present; pipeline schema not fully aligned
│
├── web/                        React + Vite (marketing at /, app at /app)
│   ├── index.html              Marketing landing
│   ├── app/index.html          SPA entry
│   └── src/
│       ├── pages/              Dashboard, NewProject, Project, Settings
│       ├── components/         Workspace tabs: Overview / Files / Rules / Analysis
│       ├── stores/             projectStore, themeStore, toastStore
│       ├── api.ts              Fetch client + case polling
│       ├── LoginPage.tsx       ORPHANED (not routed)
│       └── SignupPage.tsx      ORPHANED waitlist-style form
│
├── landing/                    LEGACY marketing copy — superseded by web/
└── tests/                      Unit tests; Band/orchestrator mocked; no API e2e
```

### 2.3 Primary Data Flow (Project Workspace)

1. User creates a **Project** (`POST /projects`) with name, address, type, jurisdiction.
2. User uploads files (`POST /projects/{id}/files`). File types gate which modules can run (zoning / building / fire / site).
3. User optionally edits **custom rules** and/or browses built-in rules (`GET/POST /projects/{id}/rules`, `suggest-rules`).
4. User runs analysis (`POST /projects/{id}/analyze` with selected modules) → creates a `PermitCase`, returns `case_id`, runs pipeline in a background asyncio task.
5. Frontend polls `GET /cases/{id}` every ~3s; partial results stream into the Analysis tab.
6. User reviews checks + package → **Approve for Filing** → audit hash recorded.
7. Optional: **Simulate City RFI** (template draft) and **Export PDF** (client-side jsPDF).

Legacy endpoints still exist for demos/tests: `POST /cases`, `POST /cases/analyze`, `GET /cases/demo/riverside`. The React app does **not** use these as the main path.

### 2.4 Analysis Pipeline (`local_runner.py`)

Local mode is the production-solid path. Specialists are **deterministic tool assemblies**, not autonomous LLM agents. LLM is optional polish only.

| Phase | Mechanism | LLM? |
|-------|-----------|------|
| Jurisdiction / zoning | `lookup_jurisdiction`, zoning rules, setbacks | Optional 1-line summary polish |
| Building / safety | egress, sprinklers, accessibility snippet checks | Optional polish |
| Site / env | flood zone, utilities | Optional polish |
| Custom rules | `custom_rules.py` evaluates user rules against findings | Yes (WARN fallback if skip/fail) |
| Package | permit catalog + fee schedule → `PermitPackage` | No |
| Conductor | merge, conflicts, readiness, audit hash | No |

`LOCAL_SKIP_LLM=1` disables all LLM calls; the pipeline still completes. LLM failures never abort analysis.

**Band mode** (`shared/band_client/orchestrator.py`) creates a real chatroom and dispatches specialists sequentially with long staggers (rate-limit survival). It is slower, less reliable, and largely untested in CI. Prefer local for product work; treat Band as a showcase path.

### 2.5 Auth (current reality)

**There is no real auth.**

- API routes are open (no JWT/API-key middleware).
- `LoginPage` / `SignupPage` / `auth.ts` exist but are **not wired** into `App.tsx` routes.
- Projects have **no `owner_id`** — every project is global to the DB instance.

Fine for hackathon demos. Not acceptable for a regulated multi-user product.

### 2.6 Jurisdiction Reality Check

| Pack | Rules preview UI | Scoring pipeline (`*_tools.py`) | Notes |
|------|------------------|----------------------------------|-------|
| `austin_tx` | Yes | Yes (assumed schema) | Only fully active end-to-end path |
| `manhattan_ks` | Strong (266 chunks, district filters) | **Fragile** — different snippet/utility key shapes can crash tools | Great content; not yet a first-class scoring pack |
| `seattle_wa` | Partial | Partial / schema-sensitive | Same risk as Manhattan |

The UI lets users pick non-Austin jurisdictions. Until tools are schema-normalized, that is a **product footgun**.

---

## 3. What Is Solid Today

Invest here; do not rewrite casually.

1. **Project workspace UX** — create project → files → rules → modular analysis → package → approve → PDF. This is the real product loop.
2. **Local deterministic pipeline** — fast, testable, LLM-optional, never hard-fails on model outages.
3. **LLM backend abstraction** — many OpenAI-compatible providers + rate limiting for multi-process Band deploys.
4. **Audit hash + audit log rows** — meaningful for the “regulated workflow” story (hash shown in UI; full audit log API underused).
5. **Manhattan rule library preview** — real depth (chunks + area filters). Pattern to generalize, then **wire into scoring**.
6. **Deploy honesty** (`docs/DEPLOY.md`) — local orchestration recommended for reliability; Band called out as harder.

---

## 4. Gaps — Product Features Currently Lacking

Ordered by how much they block a real developer workflow (not vanity features).

### P0 — Trust & correctness (fix before marketing more cities)

| Gap | Why it hurts | Rough fix |
|-----|--------------|-----------|
| Non-Austin analysis can crash or silently mis-score | Tools assume Austin JSON key/id shapes | Define Pydantic schemas for each knowledge file; validate packs at startup; replace hard `next(...id==)` / key access with safe lookups + `data_gaps` / WARN |
| Jurisdiction picker overpromises | UI offers Manhattan/Seattle as if pipeline-ready | Gate `coverage_status` in analyze API: refuse or force “preview-only” until pack is certified |
| Auth disconnected / API open | Anyone with URL can read/mutate all projects | Wire real auth or temporarily disable orphaned login UI + add at least API-key / single-tenant lock for shared deploys |

### P1 — Core product depth (what users expect after first wow)

| Gap | Why it hurts | Rough fix |
|-----|--------------|-----------|
| No accounts / orgs / ownership | Cannot sell SaaS; no collaboration | `users` + `orgs` tables; `owner_id`/`org_id` on `Project`; JWT or session cookies; RBAC (viewer/editor/approver) |
| No real plan / PDF parsing | Upload is storage + gating, not geometry extraction | Phase 1: PDF text extract → structured fields; Phase 2: table detection for setbacks/parking; defer full CAD/BIM |
| RFI is a fixed template | Undermines “Packager drafts response” claim | LLM draft conditioned on case findings + user RFI text; store RFI thread on case; show history in Analysis tab |
| Audit log not in UI | Backend exists; compliance story incomplete | Simple timeline component on Analysis/Overview calling `GET /cases/{id}/audit` |
| Document checklist is module-gating only | No persistent “ready to file” checklist over time | Persist package `documents_required` as checklist items with status (missing/uploaded/waived); map uploads → checklist rows |
| Revision / resubmittal history | Each case is isolated; no diff | Link cases under a project; “compare run A vs B” on check statuses + conflicts |

### P2 — Differentiation & scale

| Gap | Why it hurts | Rough fix |
|-----|--------------|-----------|
| Static knowledge ages out | Codes amend; overlays missing | Ingest → chunk → embed (Chroma first); retrieve top-K at analysis; LLM applies to brief (Manhattan chunks are the prototype) |
| Band mode unreliable / sequential | Demo risk; minutes of latency | Either commit: sandbox integration tests + batch specialist asks; or officially demote Band to optional showcase and parallelize local tools with `asyncio.gather` |
| Framework diversity claim outdated | README still implies CrewAI/PydanticAI diversity | All agents share LangGraph factory — update marketing or actually diversify |
| No notifications / deadlines | Users leave and forget fee/filing dates | Email/webhook on analysis complete + approve; optional calendar fields from package timeline |
| No city e-filing | Expected eventually; correctly out of scope now | Keep out of MVP; later: export packages in AHJ-specific packet formats before true API submit |
| Dead / legacy surfaces | Confuses contributors | Remove or quarantine `landing/`, `permit_review_service.py`, orphaned Login/Signup; clarify `/cases` as legacy/demo |

### P3 — Platform maturity

| Gap | Rough fix |
|-----|-----------|
| SQLite + ad-hoc migrations only | Alembic + Postgres for any multi-user deploy |
| Unit tests only; Band/orchestrator mocked; no API e2e | `httpx.AsyncClient` flow: create project → upload brief → analyze → poll → approve (`LOCAL_SKIP_LLM=1`); one smoke test per jurisdiction pack |
| Runtime artifacts in tree | Ensure `permitos.db`, `uploads/` gitignored / cleaned |
| Orchestration mode opaque in UI | Surface `band_orchestrated` / `local_fallback` badge so judges and users know which path ran |

---

## 5. Where We Should Focus Next

Think of this as a sequenced roadmap, not a feature wishlist. Each phase unlocks the next.

### Phase A — Make multi-city safe (1–2 weeks)

**Goal:** Picking Manhattan or Seattle never crashes; Austin remains gold standard.

1. **Knowledge schema contract** — Pydantic models for `zoning_rules`, `building_code_snippets`, `utility_requirements`, `environmental_triggers`, `fee_schedule`, `permit_catalog`.
2. **Validate on startup / CI** — fail fast with a clear pack error, not `StopIteration` mid-case.
3. **Tool adapters** — per-pack normalizers *or* rewrite JSON packs to one canonical shape; prefer one shape + migration script.
4. **Integration tests** — `run_local_case()` for `austin_tx`, `manhattan_ks`, `seattle_wa` with `LOCAL_SKIP_LLM=1`.
5. **API gate** — `coverage_status != active` → 422 or “rules preview only” unless `allow_experimental=1`.

**Why first:** Expanding marketing cities without this creates demos that break. Trust > breadth.

### Phase B — Close the product loop for one power user (2–3 weeks)

**Goal:** A single developer org can use this weekly without shame.

1. **Real auth + project ownership** (even email/password + org of one).
2. **Wire audit timeline UI**.
3. **Replace RFI template** with case-aware LLM draft + stored history.
4. **Persistent document checklist** tied to package requirements + uploaded files.
5. **Kill orphaned login/signup** or finish wiring them — no half-auth.

**Why second:** Turns the polished analysis UI into a retained workspace, not a one-shot demo.

### Phase C — Deeper intelligence (3–5 weeks)

**Goal:** Analysis quality jumps for edge cases without abandoning deterministic checks.

1. **Hybrid pipeline:** keep deterministic checks as the skeleton; add a second LLM pass that (a) retrieves code chunks, (b) proposes additional WARN/FAIL with citations, (c) never overrides a deterministic FAIL without a “LLM override” flag.
2. **Promote Manhattan chunks → retrieval layer** (Chroma locally). Same ingest pattern for Austin LDC / Seattle.
3. **PDF text intake** for briefs and narrative sheets (not full CAD yet).
4. **Conflict remediation** — LLM suggests variance vs redesign paths with timeline deltas (upgrade `detect_conflicts()` beyond hardcoded rules).

**Why third:** Quality differentiation. Do this after the product is safe and sticky.

### Phase D — Band & multi-agent story (optional fork)

**Only invest if Band remains a prize/demo requirement.**

1. Integration test against mocked Band REST (dispatch + poll + normalize).
2. Reduce sequential stagger; batch specialist prompts where rate limits allow.
3. Surface orchestration mode in UI.
4. Otherwise: keep Band as `docs/DEPLOY.md` Option B and put engineering into local parallelization.

### Phase E — Scale jurisdictions (ongoing)

| Approach | When | Effort |
|----------|------|--------|
| Canonical JSON packs + schema validation | Now → 5 cities | Days per city once schema exists |
| Chunk ingest + RAG (Manhattan pattern) | Complex codes / frequent amendments | 1–2 weeks to generalize ingest |
| Live city GIS / permit APIs | After product-market fit | Per-city integration projects |

Do **not** add a fourth city until Phase A is done for the three packs already in-repo.

---

## 6. Improving Evaluation Quality (Technical Notes)

### 6.1 Current strengths

- Deterministic tools → predictable demos and cheap CI (`LOCAL_SKIP_LLM=1`).
- Structured Pydantic reports → UI and PDF can render citations reliably.
- Custom rules give power users an escape hatch without forking the knowledge pack.

### 6.2 Current weaknesses

- Knowledge is static and Austin-shaped in the tool layer.
- Conflict detection is shallow / largely hardcoded.
- LLM mostly polishes prose; it does little real cross-domain reasoning.
- Uploaded drawings are not understood — only tagged for module readiness.

### 6.3 Recommended evaluation architecture (target)

```
ProjectBrief + files
        │
        ├─► Deterministic tools (canonical knowledge schema)  → hard FAIL/PASS
        ├─► RAG retrieve top-K code chunks (city pack)        → LLM structured extras
        ├─► Custom rules eval                                → WARN/FAIL
        └─► Conductor: merge + conflict LLM pass + package
```

Rules of the road:

- Deterministic FAIL always wins (safety / setbacks).
- LLM findings are labeled `source: llm_rag` vs `source: tool`.
- Every finding needs a citation string or is dropped to WARN/`data_gap`.

---

## 7. Running Locally

### Backend

```bash
cd permit_os
pip install -e ".[dev]"
cp .env.example .env   # configure LLM_* as needed
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd permit_os/web
npm install
npm run dev    # → http://localhost:5173
```

| URL | What |
|-----|------|
| `http://localhost:5173/` | Marketing |
| `http://localhost:5173/app/` | Product (dashboard → projects) |

Prefer `PERMITOS_ORCHESTRATION=local` for day-to-day. Use Band only with valid `agent_config.yaml` and awareness of rate limits.

### Useful env vars

| Variable | Purpose |
|----------|---------|
| `LLM_BACKEND` / `LLM_MODEL` / provider keys | Executive polish + custom rules |
| `LOCAL_SKIP_LLM=1` | Deterministic-only runs / tests |
| `PERMITOS_ORCHESTRATION` | `local` \| `band` \| `auto` |
| `PERMITOS_VIDEO_MODE=1` | Fast local demo path |
| `DATABASE_URL` | Default SQLite aiosqlite |

### Tests

```bash
cd permit_os
LOCAL_SKIP_LLM=1 python -m pytest tests/ -q
```

Current suite is mostly unit-level. Adding project→analyze API e2e should be a near-term CI goal.

---

## 8. Contributor Decision Guide

When unsure where to put effort:

| If you want… | Do this |
|--------------|---------|
| Fewer broken demos | Phase A (schema + gates + tests) |
| Something users return to | Phase B (auth, checklist, RFI, audit UI) |
| Smarter analysis | Phase C (RAG hybrid, PDF text) |
| Hackathon Band story | Phase D only with explicit demo need |
| More cities on the landing page | **Refuse** until Phase A green for existing packs |

**Anti-goals (still correct):**

- Auto-submit to city portals
- Perfect CAD/BIM understanding in the next sprint
- Pretending Band is the default reliable path when local is

---

## 9. Team

- Muhammad Shoaib
- Sibtain Ahmed
- Azeem Kamran
- Hasnain Ahmed
