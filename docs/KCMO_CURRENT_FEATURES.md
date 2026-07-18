# Kansas City, MO (KCMO) — Current Feature Status

> Inventory of what EstatePermit / PermitOS supports today for **Kansas City, Missouri** (`kansas_city_mo`).  
> Last reviewed against the codebase: July 2026.

**Scope note:** This document is about **Kansas City, Missouri (KCMO)** — not Kansas City, Kansas (KCK) and not Manhattan, KS. Those are separate jurisdictions. The product explicitly **rejects KCK addresses** when KCMO rules are selected.

**Related docs**

- Product roadmap: [`EstatePermit_KCMO_Five_Step_Implementation_Plan.md`](./EstatePermit_KCMO_Five_Step_Implementation_Plan.md)
- System-wide architecture: [`../ARCHITECTURE.md`](../ARCHITECTURE.md)

---

## Snapshot

| Area | Status |
|------|--------|
| Intake (development type + work scope) | **Fully implemented** |
| KCMO vs KCK address guard | **Fully implemented** |
| Live GIS zoning lookup (KCMO) | **Fully implemented** |
| Explainable permit-bundle recommendation | **Fully implemented** |
| Persistent `ProjectPermit` records + Permits UI | **Fully implemented** (MVP) |
| Manual CompassKC / lifecycle tracking fields | **Fully implemented** (manual only) |
| Zoning review-rule generation for many districts | **Mostly implemented** |
| Document readiness / checklist states | **Under-implemented** |
| Dependency enforcement & progress intelligence | **Under-implemented** |
| KCMO-aware compliance analysis pipeline | **Under-implemented / Austin-shaped** |
| Corrections, inspections, submission package | **Missing** |
| CompassKC sync, reminders, e-filing | **Missing** |

**Rough roadmap alignment**

- **Steps 1–3** of the five-step plan → largely in place for an MVP contractor workflow  
- **Steps 4–5** → mostly not built yet  

---

## 1. Fully implemented features

These work end-to-end for KCMO projects today (create → recommend → confirm → track manually).

### 1.1 Project intake for KCMO

| Feature | Evidence / notes |
|---------|------------------|
| Default jurisdiction is Kansas City, MO | `NewProjectPage` defaults to `kansas_city_mo` |
| Development type selection | Renamed UX “Development type”; commercial TI, new commercial, multifamily, mixed-use, etc. |
| Structured work-scope checkboxes | New construction, addition, alteration, trades, fire, signs, grading, ROW, solar/EV, water/sewer, change of use |
| Optional file upload at create time | Project files stored on the project |
| Address quality guidance | UI asks for street, city, state, ZIP so parcel/zoning can resolve |

### 1.2 KCMO knowledge pack (core)

Location: `knowledge/missouri/kansas_city/`

| Asset | Status |
|-------|--------|
| `metadata.json` | Present (`coverage_status: mvp`, CompassKC portal) |
| `permit_catalog.json` | Present — building, electrical, plumbing, mechanical, fire protection, CO, land disturbance, ROW, sign |
| `document_requirements.json` | Present — per-permit document lists |
| `zoning_rules.json` | Present — detailed structured rules (e.g. DC-15); supplemented by code-generated rules |

Catalog entries include agency, portal URL, applicability triggers, dependencies, estimated fees, inspections list (as data), and source URLs.

### 1.3 Jurisdiction safety

| Feature | Behavior |
|---------|----------|
| Reject Kansas City, **Kansas** under KCMO | API returns 400 if address looks like KCK / `, KS` while jurisdiction is `kansas_city_mo` |
| Jurisdiction-neutral workflow shell | Same project/permit UI; KCMO content loaded from the knowledge pack |

Covered by tests in `tests/test_kcmo_project_permits.py`.

### 1.4 Live address → zoning resolution

| Feature | Behavior |
|---------|----------|
| Geocode project address | ArcGIS World Geocoder |
| Query KCMO zoning GIS | `mapd.kcmo.org` Zoning MapServer |
| Persist zoning profile on project | District (`CLASSIFICATION`), land use, ordinance, match score, matched address |
| Surface warnings in UI | Invalid / low-confidence / retry flows on Overview |
| Deep link to Parcel Viewer | Public source URL with address param |
| Re-resolve zoning | “Check again” on Overview / after address edit |

Implementation: `api/services/zoning_service.py` (`kansas_city_mo` config).

### 1.5 Explainable permit-bundle recommendation

| Feature | Behavior |
|---------|----------|
| Load KCMO permit catalog | From knowledge pack |
| Match development type + scope → candidate permits | Required vs likely required |
| Human-readable reason | e.g. “applies because confirmed scope: electrical work” |
| Recommendation evidence JSON | Catalog rule + project facts + match result (for audit/debug) |
| Scope changes update system recommendations | Removed scope marks system permits `not_required` without destroying user-managed records |
| Manual permits preserved | Origin `manual` / user-managed statuses not overwritten |

Implementation: `api/services/project_service.py` (`_candidate_permit_recommendations`, `_sync_project_permit_recommendations`).  
Tests cover TI + trades bundles and “removed scope” behavior.

### 1.6 Persistent permit records (Step 2)

`ProjectPermit` model fields that are wired and usable:

- Permit type / name / authority / jurisdiction  
- Requirement status (suggested, required, likely required, not required, …)  
- Lifecycle status (not started → finaled / cancelled / expired, etc.)  
- Origin (`system` vs `manual`)  
- Reason + recommendation evidence  
- Source + CompassKC portal URL  
- Dependencies (stored as data)  
- Required documents (string list)  
- Assigned employee / contractor  
- Estimated fee  
- Application number (manual CompassKC number)  
- Current blocker / next action  
- Create / update timestamps  

API: `POST/PATCH /projects/{id}/permits` (via project routes).

### 1.7 Permit Bundle workspace (Step 3 MVP)

Primary tab: **Permits** (`PermitBundleTab`).

| Feature | Status |
|---------|--------|
| List all recommended / confirmed permits | Yes |
| Summary counts (recommended, required, submitted+, N/A) | Yes |
| Confirm permit as required | Yes |
| Mark not applicable | Yes |
| Manually add a missing permit | Yes |
| Edit lifecycle status | Yes (manual dropdown) |
| Assign internal owner / contractor | Yes |
| Record CompassKC application number | Yes |
| Record blocker + next action | Yes |
| Show required-document list | Yes (static list) |
| Show dependencies + estimated fee | Yes (display) |
| Open CompassKC portal link | Yes |
| Per-permit “Review checks” drawer | Yes — pulls zoning/built-in rules relevant to that permit type |

Project shell tabs: **Overview · Permits · Documents · Review · Activity**.

### 1.8 Zoning rule library for review (KCMO)

| Feature | Status |
|---------|--------|
| Generate automatic zoning rules from GIS classification | Yes — `api/services/kcmo_zoning_rules.py` |
| Coverage across R / OB / D / M / special / overlay families | Yes for many common classifications |
| Attach rules into project rule library for review UI | Yes — `_build_kcmo_rule_library` |
| Split zoning (e.g. `R-5/R-0.5/M1-5/US`) | Supported in generator + tests |

### 1.9 Project Documents tab (basic)

| Feature | Status |
|---------|--------|
| Upload / list / delete project files | Yes |
| Tag file type + label + review areas | Yes |
| Shared project-level storage | Yes |

---

## 2. Under-implemented features

Present in some form, but incomplete, shallow, or not KCMO-correct enough for production trust.

### 2.1 Document readiness (Step 4 — partial)

| What exists | What’s incomplete |
|-------------|-------------------|
| Static “required documents” strings on each permit | No `required / received / under review / accepted / rejected / superseded` states |
| Project file uploads | No `PermitDocumentLink` — files are not formally linked to permit requirements |
| `missingDocumentCount` in API payload | Currently equals `len(required_documents)` — **not** a real missing-doc calculation |
| Document taxonomy in FILE_TYPES | Missing many KCMO types from the plan (contractor license, energy docs, response-to-comments, issued permit, inspection report, etc.) |

### 2.2 Dependencies & blockers (partial)

| What exists | What’s incomplete |
|-------------|-------------------|
| Catalog `dependencies` stored and shown | No automatic “blocked until parent issued/submitted” enforcement |
| Manual `currentBlocker` / `nextAction` fields | No computed project progress from real dependency graph |
| Parent permit field on model | Not a first-class UX for parent/child permits |

### 2.3 Permit detail workspace (partial)

Plan calls for per-permit Overview / Requirements / Documents / Corrections / Inspections / Activity.

**Today:** one card per permit with collapsed “Review checks” + “Permit tracking” sections. No separate correction or inspection sub-workspaces.

### 2.4 Lifecycle & fees (partial)

| What exists | What’s incomplete |
|-------------|-------------------|
| Full lifecycle status enum in UI | Status is **manual**; nothing syncs from CompassKC |
| Estimated fee from catalog | No actual fee entry UI; no KCMO fee-schedule engine |
| Model fields for issued number / dates | Little or no UI for issuance/expiration dates |
| Inspections listed in catalog JSON | Not turned into trackable inspection records |

### 2.5 KCMO compliance / analysis pipeline (weak for KCMO)

The **Review** tab still runs the shared analysis pipeline (`local_runner` / modules: zoning, building, fire, site).

| Reality for KCMO | Impact |
|------------------|--------|
| Knowledge pack **lacks** `fee_schedule.json`, `building_code_snippets/`, `environmental_triggers.json`, `utility_requirements.json` | Deterministic building/site/packager tools are still largely **Austin-shaped** |
| `jurisdiction_tools.lookup_jurisdiction()` still keys off Austin demo addresses | Analysis path is not a true KCMO code engine |
| Zoning GIS + `kcmo_zoning_rules` are strong | That strength is mainly in **rules preview / Review checks**, not a full multi-discipline KCMO scorer |

**Verdict:** Permit-bundle product for KCMO is real; deep multi-discipline “compliance report” for KCMO is **not** at Austin-parity.

### 2.6 Activity history (minimal)

| What exists | What’s incomplete |
|-------------|-------------------|
| Activity tab shows project created + past review runs | No full audit of confirm/dismiss, status changes, assignments, exports |
| Case `audit_log` exists for analysis cases | Not surfaced as a rich project/permit activity feed |

### 2.7 Knowledge depth (MVP, not complete code)

| What exists | What’s incomplete |
|-------------|-------------------|
| MVP catalog of common commercial / trade / CO / grading / ROW / sign permits | Not every KCMO permit type / information bulletin |
| Generated zoning standards for many district families | Not full Chapter 88 text; limited overlays/use conditions |
| `zoning_rules.json` sample depth (e.g. DC-15) | Not every downtown/residential district fully authored as JSON |
| Sources + `last_verified` dates on pack | No automated freshness monitoring against Municode / IBs |

### 2.8 Applicability intelligence (partial)

| What exists | What’s incomplete |
|-------------|-------------------|
| Scope checkboxes drive catalog triggers | No follow-up applicability questions / exemptions engine |
| Classifications: required / likely required / not required | Softer states (`needs_confirmation`, `optional`) exist in enum but are barely used by the recommender |
| Explainable reasons | No confidence score or “uncertain — verify with city” UX beyond zoning warnings |

---

## 3. Missing features

Not implemented for KCMO (or only mentioned in plans / Settings “coming soon”).

### 3.1 Document & correction lifecycle (Step 4)

- `PermitDocumentLink` entity (one file → many permits)  
- Document versioning / supersede flow  
- Structured **correction items** (department, comment, due date, round, resolution)  
- **Review All Permits / Review This Permit** that attach findings to permit records (today’s Review tab is analysis-case oriented)  
- Blockers derived from missing/rejected documents  
- Frozen **Ready for Human Review → Ready for Submission** snapshot  
- **Submission Readiness Package** (cover summary, permit register, checklists, ZIP folders, readiness PDF)

### 3.2 Inspections & closeout (Step 5)

- `PermitInspection` records (type, schedule, result, reinspection)  
- Payment status tracking  
- Expiration reminders  
- Certificate of Occupancy as a project-level completion gate (beyond a catalog row)  
- Failed inspection → reinspection workflow  

### 3.3 Portal operations

- Automated CompassKC status sync  
- Deep status scraping / supported API integration  
- Reminders for portal checks, unanswered corrections, upcoming inspections  
- Auto-submit / pay / sign applications (**explicit non-goal for MVP**; still missing even as assisted packet export)

### 3.4 Knowledge & intelligence gaps

- Full KCMO building / fire / site / utilities structured packs for the analysis tools  
- RAG over KCMO Zoning & Development Code + Information Bulletins  
- Contractor license validation against KCMO licensing data  
- Historical permit replay / accuracy benchmarking against open permits dataset  
- Overlay / airport height / historic district special handling beyond basic GIS fields  

### 3.5 Product platform gaps (affect KCMO users)

- Real authentication, orgs, RBAC  
- Multi-user collaboration / comments  
- Email / webhook notifications  
- Kansas City, **Kansas** or Johnson County packs (intentionally out of KCMO scope)  

---

## 4. Feature matrix (quick reference)

| Feature | Fully done | Partial | Missing |
|---------|:----------:|:-------:|:-------:|
| Development type + scope intake | ✓ | | |
| KCMO knowledge: permit catalog | ✓ | | |
| KCMO knowledge: document lists | ✓ | | |
| Reject KCK under KCMO | ✓ | | |
| GIS zoning resolve + warnings | ✓ | | |
| Explainable permit recommendations | ✓ | | |
| Persistent `ProjectPermit` | ✓ | | |
| Confirm / dismiss / manual add | ✓ | | |
| Manual lifecycle + CompassKC number | ✓ | | |
| Permits tab workspace | ✓ | | |
| Generated zoning review rules | ✓ | | |
| Project file upload | ✓ | | |
| Document ↔ permit linking & states | | ✓ | |
| Dependency-driven blockers | | ✓ | |
| Real missing-doc counts | | ✓ | |
| Per-permit corrections/inspections UI | | ✓ | |
| KCMO building/fire/site analysis packs | | ✓ | |
| Activity / audit feed (full) | | ✓ | |
| Fee schedule engine | | | ✓ |
| Submission readiness ZIP/PDF package | | | ✓ |
| Inspection tracking entities | | | ✓ |
| CompassKC sync / reminders | | | ✓ |
| Auth / org tenancy | | | ✓ |
| E-file to city | | | ✓ |

---

## 5. What to build next (KCMO-specific)

Recommended order if the goal is a contractor-usable KCMO product:

1. **Document checklist states + link uploads to permits** — makes the Permits tab operationally honest.  
2. **Auto-blockers from dependencies + missing docs** — replace fake `missingDocumentCount`.  
3. **KCMO analysis packs** (building / fire / site / fees) or gate Review modules until packs exist — stop implying Austin-depth scoring.  
4. **Correction items + human “ready to submit” gate** — Step 4 MVP.  
5. **Submission readiness export** (PDF + file index) before any CompassKC automation.  
6. **Inspections + expiration reminders** only after issuance tracking is used in pilots.

---

## 6. Key code & data pointers

| Area | Path |
|------|------|
| KCMO knowledge pack | `knowledge/missouri/kansas_city/` |
| Zoning GIS + geocode | `api/services/zoning_service.py` |
| Zoning rule generator | `api/services/kcmo_zoning_rules.py` |
| Permit recommend + sync | `api/services/project_service.py` |
| `ProjectPermit` model | `api/models.py` |
| Permits UI | `web/src/components/permits/PermitBundleTab.tsx` |
| Intake UI | `web/src/pages/NewProjectPage.tsx` |
| Workspace tabs | `web/src/components/projects/ProjectWorkspace.tsx` |
| KCMO tests | `tests/test_kcmo_project_permits.py`, `tests/test_zoning_service.py` |
| Five-step plan | `docs/EstatePermit_KCMO_Five_Step_Implementation_Plan.md` |
