# EstatePermit Dashboard MVP Plan

## Goal

Build the next version of EstatePermit as a `project-first dashboard` with `auto-generated permit cards` for one city and one narrow project scope.

This MVP should answer four questions for a user:

1. What kind of project is this?
2. Which permits likely apply in this city?
3. What documents are missing for each permit?
4. What issues may delay approval before submission?

## Product Decision

We will build:

- `1 city` for the first serious MVP
- `1 project type`
- `4-6 permit cards`
- `AI + rules` instead of a single large prompt

Recommended MVP scope:

- City: `Seattle`
- Project type: `Commercial Tenant Improvement`
- Permit cards:
  - Building / Construction
  - Mechanical
  - Plumbing
  - Electrical
  - Fire Alarm / Fire Suppression
  - Right-of-Way only when relevant

Why this scope:

- It is easier to pitch to small and medium firms.
- It reflects real permit workflow better than one combined review.
- It is narrow enough to ship without turning into a generic compliance platform.

## Current Repo Position

The repo already has a strong starting point:

- Frontend project dashboard in `web/src/pages` and `web/src/components`
- Project workspace with tabs for `Overview`, `Files`, `Rules`, and `Analysis`
- Backend project and analysis routes in `api/routes/projects.py`
- Stored project, file, and case models in `api/models.py`
- Existing permit analysis flow and permit package output

This means we should `extend the current dashboard`, not replace it.

## MVP Outcome

After implementation, a user should be able to:

1. Create a project
2. Upload project files
3. Choose Seattle + Commercial TI
4. Run analysis
5. See permit cards generated for that project
6. Open each permit card to view:
   - required documents
   - matched uploaded documents
   - missing items
   - AI findings
   - status
7. See cross-permit conflicts and overall readiness

## What We Are Building

### 1. Dashboard Structure

We will shift from a mostly automated-report view to a `permit workspace`.

Main project page layout:

- `Project Header`
  - name
  - address
  - city
  - project type
  - overall readiness
- `Project Summary`
  - AI-generated brief
  - extracted project facts
- `Permit Cards Section`
  - one card per likely permit
- `Cross-Permit Issues`
  - contradictions and blockers across permits
- `Submission Readiness`
  - high-level final status and next steps

### 2. Permit Card Model

Each permit card should contain:

- permit name
- agency / reviewer group
- status: `ready`, `missing_docs`, `needs_review`, `high_risk`
- why this permit applies
- required document checklist
- uploaded documents mapped to this permit
- missing documents
- findings
- recommended actions

### 3. Analysis Flow

We will replace the current "all findings into one final package" mindset with a 4-step pipeline:

1. `Project Extraction`
2. `Permit Detection`
3. `Per-Permit Review`
4. `Cross-Permit Consistency Check`

This is the core product change.

## Implementation Plan

### Phase 1. Lock MVP Scope

Before writing more product logic:

- lock city to `Seattle`
- lock project type to `Commercial Tenant Improvement`
- define the initial permit set
- collect Seattle requirements for each permit track

Deliverables:

- Seattle permit catalog JSON
- permit-specific requirement templates
- document type vocabulary for Seattle TI projects

Suggested files:

- `knowledge/seattle/permit_catalog.json`
- `knowledge/seattle/document_requirements.json`
- `knowledge/seattle/metadata.json`

### Phase 2. Data Model Changes

We need first-class permit objects in the backend results.

Add a new result shape that supports permit cards:

- `project_summary`
- `project_facts`
- `candidate_permits`
- `permit_reviews`
- `cross_permit_issues`
- `submission_readiness`

Recommended shape:

```json
{
  "project_summary": {},
  "project_facts": {},
  "candidate_permits": [
    {
      "permit_key": "fire_suppression",
      "label": "Fire Alarm / Fire Suppression",
      "agency": "Fire",
      "reason": "Commercial TI with life-safety scope detected"
    }
  ],
  "permit_reviews": [
    {
      "permit_key": "fire_suppression",
      "status": "missing_docs",
      "required_documents": [],
      "matched_documents": [],
      "missing_documents": [],
      "findings": [],
      "next_actions": []
    }
  ],
  "cross_permit_issues": [],
  "submission_readiness": {}
}
```

Backend tasks:

- extend Pydantic schemas in `shared/schemas`
- extend stored case result shape in `api/models.py`
- update serializers returned by project analysis endpoints

### Phase 3. Permit Knowledge Layer

This is where product quality will come from.

For Seattle commercial TI, define:

- permit applicability triggers
- required docs per permit
- optional docs
- blocker conditions
- common rejection issues

This should be `rules-first`.

AI should help:

- classify project facts
- map files to permits
- explain findings

AI should not decide everything from scratch.

### Phase 4. Project Extraction Pipeline

The first analysis step should generate a canonical project profile from uploaded docs.

Extract fields such as:

- project name
- address
- occupancy / use
- TI vs new construction
- square footage
- trades involved
- fire/life-safety scope
- utility or street impact

Implementation tasks:

- add project extraction schema
- parse project brief JSON if present
- fall back to uploaded files and AI extraction if needed
- store extracted facts in case results

Output should be one clean normalized object used by later stages.

### Phase 5. Permit Detection Service

Create a service that takes:

- jurisdiction
- project type
- extracted project facts

and returns:

- likely permits
- reasons each permit applies
- confidence / certainty level

Implementation tasks:

- add permit detection module in `api/services` or `shared/tools`
- use Seattle rules plus extracted facts
- optionally ask AI to confirm gray-area cases

This service drives the dashboard cards.

### Phase 6. Per-Permit Review Pipeline

For each detected permit:

- load requirement template
- map uploaded files to required documents
- identify missing docs
- run focused review for that permit only
- generate findings and next steps

Implementation tasks:

- add per-permit review schema
- build document-to-permit mapping logic
- add one review function per permit type, or one generic engine with permit templates
- generate permit-specific status

This is the highest-value part of the MVP.

### Phase 7. Cross-Permit Consistency Check

After reviewing each permit independently, compare them.

Check for:

- inconsistent address
- inconsistent project description
- inconsistent square footage
- conflicting occupancy assumptions
- missing trade scope in one permit but present in another

Implementation tasks:

- add cross-permit issue schema
- implement consistency checks after all permit reviews complete
- expose issues in final dashboard summary

### Phase 8. Frontend Dashboard Upgrade

We should build on the existing `ProjectWorkspace` and `AnalysisTab`.

UI changes:

- keep existing project page structure
- replace or expand the current analysis tab with:
  - project summary panel
  - permit cards grid
  - permit detail drawer or modal
  - cross-permit issues panel
  - readiness summary panel

Recommended component additions:

- `web/src/components/permits/PermitCard.tsx`
- `web/src/components/permits/PermitGrid.tsx`
- `web/src/components/permits/PermitDetailPanel.tsx`
- `web/src/components/permits/ReadinessSummary.tsx`
- `web/src/components/permits/CrossPermitIssues.tsx`

Existing components likely to update:

- `web/src/components/analysis/AnalysisTab.tsx`
- `web/src/types/index.ts`
- `web/src/stores/projectStore.ts`
- `web/src/api.ts`

### Phase 9. Status System

We need statuses that make sense to a non-expert user.

Per permit:

- `ready`
- `missing_docs`
- `needs_review`
- `high_risk`

Project-level:

- `ready_to_prepare`
- `needs_more_documents`
- `needs_project_changes`
- `high_submission_risk`

These should be visible in cards and in the project summary.

### Phase 10. Demo Data and Pitch Readiness

We should prepare at least 2 clean demo projects:

- a mostly complete Seattle commercial TI project
- an incomplete Seattle commercial TI project with missing fire / MEP items

That gives a clear before/after story in demos.

Deliverables:

- sample project briefs
- sample uploaded file sets
- one happy path
- one risk path

## Build Order

This is the recommended order of execution.

### Step 1. Scope and knowledge setup

- finalize Seattle TI permit catalog
- define requirement templates
- define output schemas

### Step 2. Backend result model

- add permit-card-oriented result structures
- store them in case results
- expose them in API responses

### Step 3. Analysis pipeline refactor

- add project extraction
- add permit detection
- add per-permit review
- add cross-permit checks

### Step 4. Frontend rendering

- update analysis tab to display permit cards
- add detail panel and readiness summary
- connect status mapping

### Step 5. Demo hardening

- add sample data
- polish copy and statuses
- make sure the dashboard tells a simple story in under 2 minutes

## Technical Notes

### Keep

- current project creation flow
- current file upload flow
- current case storage approach
- existing analysis history

### Change

- analysis output shape
- analysis tab UI
- permit package section into permit-card workflow
- jurisdiction knowledge from Austin-centered output toward Seattle TI output

### Do Not Do Yet

- multi-city support
- all project types
- direct city portal filing
- full code-compliance engine
- deep OCR-heavy document intelligence
- enterprise workflow management

## Suggested Milestones

### Milestone 1

Seattle TI rules exist and backend can return detected permits.

### Milestone 2

Backend returns permit review objects with statuses and missing docs.

### Milestone 3

Frontend shows permit cards and permit detail views.

### Milestone 4

Cross-permit issues and overall readiness are visible.

### Milestone 5

Demo-ready sample projects and a clean pitch flow are complete.

## Final MVP Definition

The MVP is done when:

- a user can upload a Seattle commercial TI project
- the app detects likely permit tracks
- the dashboard creates permit cards automatically
- each card shows missing documents and key risks
- the app highlights cross-permit conflicts
- the user can understand submission readiness without being a permit expert

## Immediate Next Task

Start with `Phase 1 + Phase 2`:

- create Seattle knowledge files
- define permit-card result schemas
- refactor backend results before touching the UI

That is the cleanest path because the dashboard should be driven by correct permit objects, not hardcoded frontend placeholders.
