# EstatePermit Architecture

## Product workflow

EstatePermit is a permit-readiness workspace for construction project teams.

1. A user creates a project with its address, development type, and jurisdiction.
2. The user selects the work planned on site, such as construction, electrical, plumbing, mechanical, fire protection, signs, grading, or utility work.
3. The user uploads plans and supporting project files.
4. EstatePermit loads the selected jurisdiction's permit catalog and recommends the applicable permit bundle with an explanation for every recommendation.
5. Each recommended permit becomes an independently managed project record after user confirmation.
6. EstatePermit loads the rules and document requirements associated with each permit.
7. The review engine uses deterministic checks and structured LLM review to evaluate the uploaded files against those requirements.
8. The product identifies missing documents, failed checks, conflicting facts, dependencies, and submission blockers.
9. After human review, EstatePermit assembles the approved files and results into a submission-ready permit document bundle.

KCMO is the first deeply supported jurisdiction. Additional cities use the same project, permit, document, review, and lifecycle model with their own verified knowledge packs.

## System overview

```text
React project workspace
        |
        | project scope, permit records, files, review actions
        v
FastAPI application
        |
        +-- Project and permit services
        +-- Jurisdiction and address resolution
        +-- Permit recommendation engine
        +-- Rule and document requirement loader
        +-- File review pipeline
        +-- Submission-readiness and bundle generation
        v
Jurisdiction knowledge packs + uploaded project files
        |
        v
SQLite today / Postgres target
```

## Primary entities

- `Project`: address, jurisdiction, development type, work scope, and overall readiness.
- `ProjectPermit`: one persistent record per applicable permit, including requirement status, lifecycle status, dependencies, ownership, fees, application number, blocker, and next action.
- `ProjectFile`: an uploaded plan or supporting document stored once at project level.
- `PermitDocumentLink`: connects a file to one or more permit requirements without duplicate uploads.
- `PermitCase`: a versioned review run and its structured results.
- `AuditLogEntry`: records material review, approval, and lifecycle events.

## KCMO permit recommendation

The Kansas City workflow distinguishes the complete city permit catalog from the smaller permit bundle applicable to a specific project. Recommendations use:

- jurisdiction and address;
- development type;
- selected site-work categories;
- structured project facts and exemptions;
- parent/child permit relationships;
- dependencies and required follow-up questions;
- official CompassKC application guidance.

Kansas City, Kansas and surrounding municipalities must never be evaluated with KCMO rules.

## File and rule review

Uploaded files are mapped to permit-specific document requirements. The review pipeline combines:

- deterministic applicability and rule checks;
- jurisdiction-specific permit and code sources;
- LLM extraction and structured comparison against uploaded file content;
- citations, confidence, and explicit data-gap handling;
- cross-permit consistency checks;
- human approval before anything is marked ready for submission.

LLM output is evidence, not authority. Unsupported findings are downgraded to a warning or data gap, and the product does not replace licensed professional review or city approval.

## Customer-facing project workspace

The primary navigation is:

- **Overview** — project scope and overall readiness.
- **Permits** — recommended and confirmed permit bundle, statuses, responsibilities, dependencies, and next actions.
- **Documents** — uploaded project files, versions, and mappings to permit requirements.
- **Review** — checks and findings organized by permit and rule.
- **Activity** — review, approval, correction, and lifecycle history.

The final output is a submission-ready bundle containing the approved documents, permit-specific checklists, cited review results, unresolved exceptions, and filing guidance.

## Safety boundaries

- EstatePermit provides pre-screening and permit-readiness assistance.
- It does not provide legal, engineering, or architectural advice.
- It does not claim that a city will approve a submission.
- Human review is required before a bundle is marked ready for submission.
- Jurisdiction sources require effective dates and periodic verification.

