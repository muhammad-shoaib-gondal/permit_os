# PermitOS — Technical Strategy & Prize Alignment

**Band of Agents Hackathon | Track 3: Regulated & High-Stakes Workflows**  
**Source:** [lablab.ai Band of Agents Hackathon](https://lablab.ai/ai-hackathons/band-of-agents-hackathon)  
**Date:** June 14, 2026

---

## 1. What the Hackathon Page Says (Extracted Facts)

### Event basics

| Item | Detail |
|------|--------|
| **Dates** | June 12–19, 2026 (online) |
| **Submission** | Through lablab.ai only; public GitHub; demo URL; 3–5 min video |
| **License** | MIT-compliant, original work |
| **Prize payout** | Up to 90 days after event |
| **Band Pro** | Promo `BANDHACK26` → 100% off 1 month Pro at band.ai |

### Core challenge (non-negotiable)

- **Minimum 3 agents** collaborating through Band
- Band must be the **active collaboration layer** — not a notification wrapper or post-hoc log
- Agents must **communicate, share structured context, delegate, hand off tasks, coordinate state**
- Cross-framework / cross-model encouraged

### Tracks (we compete in Track 3)

| Track | Focus |
|-------|--------|
| Track 1 | Internal enterprise workflows (HR, finance, procurement) |
| Track 2 | Multi-agent software development (Codeband reference) |
| **Track 3** | **Regulated & high-stakes** — traceability, escalation, careful decisions |

Track 3 examples on the page: healthcare coordination, financial approvals, legal/contract review, insurance claims, **compliance / risk investigation**.

**PermitOS fit:** Real estate permitting = compliance-heavy, citation-required, human gate, audit trail. Directly analogous to submitted projects like *MediChain AI Prior Auth Review*, *Compliance Guardian*, *Band Decision Desk*, *PactWarden*.

### Judging criteria (how we score)

1. **Application of Technology** — Band as coordination bus; visible handoffs, shared context, role specialization, task state
2. **Presentation** — Problem, agent roles, Band’s role, context flow, enterprise value — easy to demo in 3–5 min
3. **Business Value** — Real workflow pain; reduces manual coordination; improves decisions
4. **Originality** — Beyond single chatbot; agents discover, coordinate, review, escalate

---

## 2. Prize Pool — Full Breakdown

### Total advertised pool: **$10,000+**

### Main hackathon prizes (overall placement)

| Place | Cash |
|-------|------|
| **1st** | **$3,500** |
| **2nd** | **$2,500** |
| **3rd** | **$1,500** |

**Total main cash:** $7,500

These are awarded for the **strongest projects overall** — not per track. Track 3 positioning helps originality and business value, but we still compete against all submissions.

### Partner prize: Best Use of AI/ML API

**Award:** One team — “strongest use of AI/ML API”

| Component | Value |
|-----------|-------|
| Cash | **$1,000** |
| AI/ML API credits | **$1,000** (continued building) |

**Eligible uses (from page):** model orchestration, reasoning, automation, **extraction**, multimodal workflows.

**Builder access (everyone):**
- **$10 credits per person** via lablab.ai coupon claim
- Up to **500 participants**
- Valid **until hackathon ends**

### Partner prize: Best Use of Featherless AI

**Award:** Top 3 Featherless projects (meaningful integration required)

| Place | Reward |
|-------|--------|
| **1st** | **500 inference credits** + Claw Pro plan (**$200 value**) |
| **2nd** | 300 inference credits + Claw Pro ($200) |
| **3rd** | 100 inference credits + Claw Pro ($200) |

**Builder access (everyone):**
- **$25 credits per participant**
- Promo code: **`BOA26`**
- Up to **1,000 participants**, first-come first-served
- **1 month** validity from activation

### Maximum realistic cash if we win big

| Award | Cash |
|-------|------|
| Main 1st | $3,500 |
| AI/ML API best use | $1,000 |
| Featherless 1st | $0 cash (credits + Claw Pro) |
| **Best-case cash total** | **$4,500** |

Plus **$1,000 AI/ML API credits**, **500 Featherless inference credits**, and **Claw Pro ($200)**.

Partner prizes are **independent** of main placement — a project can win main 2nd *and* AI/ML API best use *and* Featherless 1st.

---

## 3. Prize-Winning Strategy for PermitOS

### Target A: Main prize ($3,500 / $2,500 / $1,500)

**What judges already rewarded** (from live submissions on the page):

- Multi-agent rooms with **@mentions** and named roles
- **Structured JSON** payloads between agents
- **Human-in-the-loop** approval with audit hash
- Clear **enterprise pain** and demo video
- Track 3 projects: compliance, prior auth, financial decision desk

**Our edge:**
- **5 agents** (exceeds 3 minimum)
- **$2.1T construction industry** + **$50K–$150K** expediter cost per project — concrete ROI
- **Austin deep jurisdiction** — quality over “generic compliance bot”
- **Intentional demo flaw** (Block B setback) → visible conflict → suggested fix → package → approve
- Band is **the workflow bus**, not API → single LLM → Band log

### Target B: AI/ML API partner prize ($1,000 + $1,000 credits)

**Judges look for:** “Strongest use” — must be **central**, **visible in demo**, **documented in README/video**.

**Recommended integration (make it undeniable):**

| Use case | Agent | AI/ML API role | Demo moment |
|----------|-------|----------------|-------------|
| **Unified model router** | All 5 agents | Single API key routes to GPT-4o, Claude, Gemini, Llama via AI/ML API | README diagram: “All inference via AI/ML API” |
| **PDF plan extraction** | Conductor / Jurisdiction | Multimodal or vision model extracts setback notes from uploaded site plan | Upload PDF → extracted “Block B 8ft” appears in feed |
| **Conflict reasoning** | Conductor | Strong reasoning model merges 3 reports, explains variance path | Conductor posts structured conflict + natural-language executive summary |
| **Fee / checklist generation** | Packager | Document generation + structured output | Package with 23 permits, $47,200 |

**Submission copy (use verbatim in lablab.ai form):**
> “PermitOS routes all agent inference through AI/ML API as a unified orchestration layer — cross-model specialists (zoning, building, site, packaging) plus multimodal PDF plan extraction and conductor merge reasoning.”

**Minimum bar:** At least **2 agents** must call AI/ML API models; **1 non-trivial feature** (PDF extract or merge reasoning) must be impossible without it.

### Target C: Featherless partner prize (500 credits + Claw Pro)

**Judges look for:** Open-source model inference integrated into agent workflow — not a one-line mention.

**Recommended integration:**

| Agent | Model (Featherless) | Why |
|-------|---------------------|-----|
| **Jurisdiction & Zoning** | `Llama-3.3-70B-Instruct` or `Qwen2.5-72B` | Open-source specialist; different from Conductor’s closed model |
| **Site / Environmental** (alt) | `DeepSeek-R1` or domain-finetuned OSS | Reasoning over environmental triggers |

**Architecture story:**
```
Band Chatroom
  Conductor     → AI/ML API (GPT-4o) — orchestration
  Jurisdiction  → Featherless (Llama 3.3) — zoning analysis
  Building      → AI/ML API (Claude) — code citations
  Site/Env      → Featherless (Qwen) — utility/flood screening
  Packager      → AI/ML API (Claude) — document generation
```

**Demo line:** “Two agents run on Featherless open-source inference; three on AI/ML API — all coordinated through Band.”

**Submission copy:**
> “Jurisdiction and Site agents use Featherless serverless inference for open-source models, demonstrating cost-efficient specialist agents alongside closed-model orchestration.”

---

## 4. Technical Architecture (Build Plan)

### 4.1 System diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  WEB UI (Next.js / Vite)                                        │
│  Intake │ Live Band feed │ Compliance │ Conflicts │ Approve      │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST + WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│  FASTAPI                                                         │
│  POST /cases │ GET /cases/{id} │ POST /approve │ audit log      │
└────────────────────────────┬────────────────────────────────────┘
                             │ triggers
┌────────────────────────────▼────────────────────────────────────┐
│  BAND CHATROOM  permit-case-{uuid}                             │
│                                                                  │
│   CONDUCTOR ──@mention──► JURISDICTION (Featherless OSS)        │
│       │                   BUILDING (AI/ML API)                   │
│       │                   SITE/ENV (Featherless OSS)             │
│       └──merge──@mention──► PACKAGER (AI/ML API)                 │
│       └──escalate──────────► HUMAN                               │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   SQLite audit          Austin KB + RAG       AI/ML API + Featherless
```

### 4.2 Five agents — frameworks, models, Band tools

| # | Agent | Framework | Primary inference | Band tools |
|---|-------|-----------|-------------------|------------|
| 1 | **Conductor** | LangGraph | AI/ML API → GPT-4o | `create_chatroom`, `add_participant`, `send_message`, `send_event`, `lookup_peers` |
| 2 | **Jurisdiction** | CrewAI or Anthropic adapter | **Featherless → Llama 3.3** | `send_message`, `send_event` |
| 3 | **Building** | LangGraph | AI/ML API → Claude | `send_message`, `send_event` |
| 4 | **Site/Env** | PydanticAI | **Featherless → Qwen 2.5** | `send_message`, `send_event` |
| 5 | **Packager** | Claude SDK / Anthropic adapter | AI/ML API → Claude | `send_message`, `send_event` |

**Cross-framework count:** LangGraph + CrewAI/PydanticAI + Anthropic = **3+ frameworks** (judge bonus).

### 4.3 Band message protocol (every agent)

```json
{
  "type": "finding | complete | question | conflict",
  "case_id": "uuid",
  "agent": "conductor | jurisdiction | building | site | packager",
  "timestamp": "ISO-8601",
  "payload": { },
  "citations": [{ "source": "Austin LDC 25-2-491", "url": "..." }]
}
```

Conductor merges only on `type: "complete"` from specialists.

### 4.4 Data models (Pydantic)

- `ProjectBrief` — intake
- `JurisdictionReport`, `BuildingSafetyReport`, `SiteEnvironmentalReport`
- `PermitCaseSummary` — conflicts, readiness, human_actions
- `PermitPackage` — permits, fees, filing_sequence, `audit_hash`

### 4.5 Knowledge layer (Austin MVP)

```
knowledge/austin/
  zoning_rules.json
  building_code_snippets/
  environmental_triggers.json
  utility_requirements.json
  permit_catalog.json
  fee_schedule.json
```

- **15–30 curated rules** with real citations (not scraped noise)
- Deterministic tools: `lookup_jurisdiction`, `calculate_setbacks`, `lookup_flood_zone`
- RAG (Chroma) over code snippets for agent grounding

### 4.6 End-to-end workflow

1. **Intake** — UI → API → Conductor creates `permit-case-{uuid}` Band room
2. **Dispatch** — Conductor `@mentions` agents 2–4 with scoped `ProjectBrief` JSON
3. **Parallel analysis** — Each posts `send_event` progress, then `type: complete` report
4. **Merge** — Conductor applies conflict rules → `NEEDS_CHANGES` for Riverside setback
5. **Package** — Conductor `@mentions` Packager → checklist, $47,200 fees, 45-day timeline
6. **Human gate** — Summary + Approve in UI (posted to Band) → `audit_hash` (SHA-256)
7. **Demo Act 2 (optional)** — Simulated city RFI → Packager drafts response

### 4.7 Track 3 compliance checklist

| Requirement | Implementation |
|-------------|----------------|
| Traceability | Every check: agent, timestamp, citation |
| Escalation | Conductor escalates blockers + final approval |
| No auto-file | Status `APPROVED_FOR_FILING` only after human click |
| Audit trail | Band message IDs + SQLite + package hash |
| Disclaimer | Visible on every report view |

---

## 5. Build Phases (7-Day Schedule)

| Day | Phase | Deliverable | Prize relevance |
|-----|-------|-------------|-----------------|
| **D1** | Foundation | Repo, schemas, Band round-trip, register 5 agents, claim **AI/ML API $10** + **Featherless BOA26** | Band depth |
| **D2** | Agent skeletons | All 5 in Band room; mock JSON; FastAPI POST/GET | Collaboration visible |
| **D3** | Specialists + KB | Austin rules; **Featherless** on Jurisdiction + Site; **AI/ML API** on Building | Partner integration |
| **D4** | Conductor + Packager | Merge, conflicts, fees; **AI/ML API PDF extract** | AI/ML API prize |
| **D5** | UI + audit | Live feed, approve button, audit hash page | Presentation |
| **D6** | Demo hardening | Riverside 10× rehearsal; record video; architecture slide | Main prize |
| **D7** | Submit | lablab.ai form, GitHub, tags: `Band`, `AI/ML API`, `Featherless`, `Track 3` | All prizes |

---

## 6. Submission Package (lablab.ai)

### Required fields

- Project title: **PermitOS — Multi-Agent Permitting Command Center**
- Short: Developer-side permitting team; 5 Band agents; Austin TX; human approval + audit trail
- Long: Problem ($50K expediter fees), architecture, Band coordination, AI/ML API + Featherless usage, demo scenario
- **Tags:** `Band`, `AI/ML API`, `Featherless`, `LangGraph`, `Track 3`, `Regulated Workflows`, `Real Estate`
- Public GitHub + demo URL
- **3–5 min video** script: problem → upload → parallel agents → setback fail → package → approve → audit hash → architecture

### README sections judges read

1. `docker compose up` or step-by-step local run
2. **Band integration** — room lifecycle, @mentions, events (with screenshots)
3. **AI/ML API** — which endpoints/models, which agents (with code links)
4. **Featherless** — which models, which agents (with code links)
5. Architecture diagram
6. Disclaimer

---

## 7. Competitive Positioning vs. Existing Submissions

| Project | Overlap | Our differentiation |
|---------|---------|---------------------|
| MediChain Prior Auth | Track 3, 5 agents, Band | **Real estate / construction** vertical; zoning + building codes |
| Compliance Guardian | Financial compliance, 3 agents | **5 agents**, deeper jurisdiction KB, fee/package output |
| Band Decision Desk | Audit hash, veto/re-plan | **Parallel specialists** + permit checklist + filing sequence |
| PactWarden | Legal adversarial agents | **Deterministic code citations** + Austin LDC, not generic legal |
| GateKeeper | Vendor risk | **Physical world** permitting — tangible developer ROI |

**Winning narrative:** “Cities are buying AI for plan review (Honolulu CivCheck). Developers still use email and expediters. PermitOS is the developer-side multi-agent permitting department — governed, cited, human-approved.”

---

## 8. Risk Register

| Risk | Mitigation |
|------|------------|
| Band SDK issues | Day 1 round-trip; record video Day 6 |
| Partner prize = checkbox only | 2 agents per partner; name APIs in demo video |
| Too many prizes, thin integration | AI/ML API = router + PDF extract; Featherless = 2 specialist agents only |
| Slow live demo | Pre-warm agents; cache RAG; deterministic fallback for setback |
| Main prize competition | Track 3 + business ROI + polished video |

---

## 9. Immediate Next Steps (No Code Yet — Decisions)

1. **Confirm team roles** — Band lead, 2 agent devs, knowledge, frontend, demo
2. **Register on lablab.ai** + Band Discord + claim **AI/ML API coupon** + activate **Featherless BOA26**
3. **Create 5 External Agents** on band.ai; save UUIDs + API keys
4. **Redeem BANDHACK26** for Band Pro
5. **Lock demo scenario** — Riverside Residences (already spec’d)
6. **Assign models:**
   - Featherless: Jurisdiction (Llama), Site (Qwen)
   - AI/ML API: Conductor, Building, Packager + PDF extraction
7. **Start Phase 1** only after above — schemas + Band round-trip

---

## 10. Quick Reference — Prizes at a Glance

```
MAIN (overall)
  1st  $3,500
  2nd  $2,500
  3rd  $1,500

AI/ML API (best use — 1 winner)
  $1,000 cash + $1,000 credits
  Builder coupon: $10/person (lablab.ai)

Featherless (top 3)
  1st: 500 credits + Claw Pro ($200)
  2nd: 300 credits + Claw Pro ($200)
  3rd: 100 credits + Claw Pro ($200)
  Builder access: $25/person, code BOA26

BAND PRO
  Code BANDHACK26 — 1 month free
```

**PermitOS prize strategy in one sentence:** Win main placement with a polished Track 3 demo of five Band-coordinated permitting agents; simultaneously make AI/ML API the unified inference + PDF extraction layer and Featherless the open-source engine for two specialist agents — document both loudly in README, tags, and video.

---

*PermitOS — Band of Agents Hackathon — Technical Strategy v1.0*
