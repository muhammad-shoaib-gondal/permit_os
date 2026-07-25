# EstatePermit: Kansas City Permit Management MVP

## Five-Step Implementation Plan

### Objective

Support one construction project with a coordinated bundle of independently managed permits.

Initial jurisdiction: **Kansas City, Missouri (KCMO)**

MVP boundary: **Steps 1–3 create the usable MVP. Steps 4–5 complete the operating lifecycle.**

## Product model

The product should follow this hierarchy:

```text
Project
└── Permit bundle
    ├── Building permit
    ├── Electrical permit
    ├── Plumbing permit
    ├── Mechanical permit
    ├── Fire-protection permit
    └── Certificate of Occupancy
```

The project describes the address, development type and complete construction scope. EstatePermit uses that information to recommend a permit bundle. Each confirmed permit then becomes an independently managed operational record.

### Important permit-catalog distinction

Selecting Kansas City activates the complete KCMO permit catalog and local guidance. It does **not** automatically mark every permit in that catalog as required. EstatePermit uses the development type, work scope, project facts, exemptions, dependencies and follow-up questions to create a candidate permit bundle.

Jurisdiction is selected or confirmed for each project. KCMO is the first deeply supported jurisdiction, not a permanent product-wide assumption. The shared project, permit, document, review and lifecycle workflow remains jurisdiction-neutral so another city can be added later through its own verified knowledge pack.

For example, if one project produces six candidate permits, the interface shows six permit records with an explanation and one of these requirement classifications:

- Suggested
- Required by confirmed facts
- Likely required
- Needs confirmation
- Optional
- Manually added
- Not required
- Removed by user

The user or a qualified reviewer confirms the working permit bundle before it becomes the project's operational workload.

### End-to-end project flow

1. Create the project and confirm the address, KCMO jurisdiction, development type and complete work scope.
2. Load the KCMO permit catalog, applicability questions, requirements, dependencies, sources and workflow guidance.
3. Generate an explainable candidate permit bundle.
4. Let the user confirm, dismiss or manually add permits.
5. Create one persistent `ProjectPermit` record for every confirmed permit.
6. Upload shared, unassigned or permit-specific documents and connect them to permit requirements.
7. Run **Review All Permits** or **Review This Permit** and attach findings to the affected project, permit, requirement or document.
8. Resolve missing documents, inconsistent facts, failed checks and correction items.
9. Move permits with no blockers to **Ready for Human Review**.
10. Require a reviewer to approve the reviewed version as **Ready for Submission** or return it for changes.
11. Generate the submission-readiness outputs and hand the user into CompassKC for filing.
12. Record application numbers and continue tracking review, corrections, issuance, inspections and closeout.

---

## Step 1: Upgrade intake and add KCMO permit knowledge

### Goal

Give the recommendation engine enough structured information to determine the complete permit bundle.

### Implementation work

- Rename **Project type** to **Development type**.
- Retain development types such as:
  - Single-family residential
  - Multifamily residential
  - Commercial tenant improvement
  - New commercial construction
  - Mixed-use
  - Industrial
- Add structured scope questions for:
  - New construction, addition, alteration, repair or demolition
  - Structural work
  - Electrical work
  - Plumbing work
  - Mechanical or HVAC work
  - Fire alarm and sprinkler work
  - Signs
  - Change of use or occupancy
  - Grading and land disturbance
  - Driveway, sidewalk and right-of-way impacts
  - Solar, batteries, generators and EV chargers
  - Water and sewer connections
- Create a `kansas_city_mo` knowledge pack containing:
  - Permit types
  - Applicability triggers
  - Applicability questions and exemptions
  - Issuing authorities
  - Parent and dependency rules
  - Required documents
  - Contractor requirements
  - Inspections
  - Source citations
- Keep the complete KCMO permit catalog separate from project applicability. The catalog defines available permit types; project facts determine which records are suggested for a specific project.
- Keep the shared project and permit workflow jurisdiction-neutral. Load the selected city's catalog, terminology, requirements, sources and portal guidance through a jurisdiction knowledge pack; ship KCMO as the first complete pack.
- Store the official permit name, aliases, supported development types, lifecycle guidance, official portal link, coverage status and last-verified source date for every supported permit type.
- Determine the municipal jurisdiction from the project address.
- Distinguish KCMO from Kansas City, Kansas and surrounding municipalities.
- Show the reason behind every recommended permit.

### Completion outcome

EstatePermit can generate an explainable KCMO permit bundle from normal project intake.

### Acceptance criteria

- A commercial tenant-improvement project with electrical, plumbing and HVAC work produces at least the building and applicable trade permits.
- Removing a declared scope removes or reclassifies the related permit recommendation.
- The user can see why each permit was recommended.
- A Kansas City, Kansas address is not evaluated using KCMO rules.

---

## Step 2: Create persistent permit records

### Goal

Convert temporary analysis recommendations into operational records that survive analysis reruns and user edits.

### Implementation work

- Add a `ProjectPermit` database entity related to `Project`.
- Store the following for every permit:
  - Permit type
  - Issuing authority
  - Jurisdiction
  - Requirement classification
  - Lifecycle status
  - Parent permit
  - Dependencies
  - CompassKC application or permit number
  - Portal URL
  - Assigned employee
  - Assigned contractor
  - Estimated and actual fees
  - Application, issuance and expiration dates
  - Current blocker
  - Next action
- Keep requirement status separate from lifecycle status.

Requirement statuses:

- Suggested
- Required
- Likely required
- Optional
- Needs confirmation
- Not required
- Removed by user

Lifecycle statuses:

- Not started
- Gathering documents
- Blocked
- Ready for human review
- Ready to submit
- Submitted
- Application accepted
- In review
- Corrections requested
- Resubmitted
- Approved
- Ready for issuance
- Issued
- Inspection phase
- Finaled
- Cancelled
- Expired

- Allow users to confirm, add or dismiss permit recommendations.
- Ensure that later analysis runs do not overwrite user-managed permit records.
- Record whether a permit originated from system analysis or was manually added.

### Completion outcome

Every recommended permit can become a durable, independently managed record.

### Acceptance criteria

- A project can contain multiple `ProjectPermit` records.
- Updating the electrical permit does not change the plumbing permit.
- Confirmed permits survive analysis reruns.
- A user-added permit remains in the bundle unless the user removes it.

---

## Step 3: Build the Permit Bundle workspace

### Goal

Make multi-permit coordination the primary day-to-day product experience.

### Implementation work

- Add a permanent **Permits** tab to every project.
- Use **Overview**, **Permits**, **Documents**, **Review** and **Activity** as the primary project navigation. Requirements, corrections and inspections remain attached to their relevant permits and can be aggregated at project level.
- Display the following for every permit:
  - Permit name
  - Authority
  - Requirement status
  - Lifecycle status
  - Responsible person
  - Contractor
  - Parent permit
  - Missing-document count
  - Current blocker
  - Next action
- Add controls to:
  - Confirm a recommendation
  - Add a missing permit
  - Mark a permit as not applicable
  - Assign an owner or contractor
  - Update lifecycle status
  - Record a CompassKC number
- Give each permit a detail workspace with:
  - Overview
  - Requirements
  - Documents
  - Review findings
  - Corrections
  - Inspections
  - Activity
- In each permit summary, show why the permit applies, its official source, submission route, coverage level, readiness, current blocker and next action.
- Treat zoning, building, fire, site and utilities as review disciplines rather than separate customer workflows.
- Visualize dependencies and blocked permits.
- Calculate overall project progress from the individual permit records.

Example:

```text
Commercial Building Permit    Corrections requested
Electrical Permit             Waiting on building permit
Plumbing Permit               Ready to submit
Mechanical Permit             Gathering documents
Fire Alarm Permit             In review
Sign Permit                   Not started
Certificate of Occupancy      Blocked
```

### Completion outcome

Users can manage the complete permit bundle while updating each permit independently.

### Acceptance criteria

- The project workspace displays every confirmed permit.
- Each permit can have a different lifecycle status and assignee.
- Dependencies clearly explain why a permit is blocked.
- The project displays a useful overall progress summary.

### MVP release gate

Release the first customer-facing MVP after this step. A contractor should be able to create a project, receive a recommended bundle, confirm the permits, assign responsibility and see blockers.

---

## Step 4: Add document readiness and correction management

### Goal

Prevent incomplete submissions and structure the review and resubmission loop.

### Implementation work

- Keep uploaded files stored once at project level.
- Add a `PermitDocumentLink` entity connecting one file to one or more permits.
- Support shared project files, permit-specific files and unassigned files. One file may satisfy requirements for multiple permits without duplicate uploads.
- Create KCMO-specific document checklists for each permit type.
- Track document states:
  - Required
  - Received
  - Under review
  - Accepted
  - Rejected
  - Superseded
- Expand the document taxonomy to include:
  - Scope-of-work letter
  - Contractor license
  - Structural calculations
  - Energy-code documentation
  - Land-disturbance plan
  - Erosion-control plan
  - Traffic-control plan
  - Sign drawings
  - Product specifications
  - Response-to-comments letter
  - Issued permit
  - Inspection report
  - Certificate of Occupancy
- Add document versioning.
- Add **Review All Permits** and **Review This Permit** actions. Project-wide checks run once and attach findings to every affected permit; permit-specific checks remain with that permit.
- Show findings as blockers, warnings, passed checks, not-applicable checks and human-review items, with the applicable requirement and source.
- Add structured correction items containing:
  - Permit
  - Reviewing department
  - Reviewer comment
  - Affected document or drawing
  - Responsible person
  - Due date
  - Resolution
  - Resubmission round
  - Status
- Generate permit-level and project-level readiness results.

### Human-review and submission output

When every required item is satisfied and no blocker remains, the system should not automatically claim that the permit is submitted or approved.

1. Change the permit to **Ready for Human Review**.
2. Let a reviewer choose **Approve as Ready for Submission** or **Return for Changes**.
3. Freeze a dated reviewed version so later document or project changes cannot silently alter the approved package.
4. Warn the user and require another review when a material change invalidates that snapshot.

Approval generates a **Submission Readiness Package** containing:

- On-screen readiness decision and blocker explanation.
- Project cover summary.
- Confirmed permit register explaining why each permit applies.
- Per-permit requirement checklists.
- Document index.
- Organized shared and permit-specific ZIP folders.
- Findings and accepted-exception report.
- Reviewer decisions and reviewed version/date.
- Official source references.
- CompassKC link and submission handoff checklist.
- Fields for application and permit numbers.
- Downloadable readiness PDF and ZIP package.

The MVP prepares and organizes the filing package. It does not automatically sign, pay or submit the application.

### Completion outcome

Teams know exactly what is missing, what was rejected and who must resolve each correction.

### Acceptance criteria

- One document can support multiple permits without duplicate uploads.
- Every required document has a visible state.
- The system prevents a permit from appearing ready when required documents are missing.
- Correction items can be assigned, resolved and linked to a resubmission.

---

## Step 5: Add inspections, completion and portal operations

### Goal

Cover the operational lifecycle from issued permit through final approval and occupancy.

### Implementation work

- Add a `PermitInspection` entity containing:
  - Permit
  - Inspection type
  - Requested date
  - Scheduled date
  - Inspector
  - Status
  - Result
  - Inspector notes
  - Failed items
  - Reinspection requirement
- Track:
  - Estimated and actual fees
  - Payment status
  - Permit issuance
  - Permit expiration
  - Required inspections
  - Final approval
  - Certificate of Occupancy
- Add reminders for:
  - Portal status checks
  - Unanswered corrections
  - Upcoming inspections
  - Permit expiration
  - Required reinspection
- Add CompassKC deep links.
- After external submission, record the application or permit number, filing date, portal status, assigned reviewer, expected response date and next follow-up without recreating the permit record.
- Maintain a complete audit and activity history.
- Treat automatic CompassKC synchronization as a later enhancement unless a stable, supported integration is available.

### Completion outcome

EstatePermit supports the complete operational lifecycle through final inspection and occupancy.

### Acceptance criteria

- Inspections are associated with the correct permit.
- Failed inspections create a visible reinspection workflow.
- A project cannot appear complete while required permits or inspections remain open.
- Certificate of Occupancy status is visible at project level.

---

## Delivery gates

### Gate 1: Permit detection works

Representative KCMO projects produce correct and explainable permit bundles.

### Gate 2: Permit records persist

Confirmed permits survive analysis reruns and retain user-entered data.

### Gate 3: MVP is usable

A contractor can create a project, confirm permits, assign work and see blockers.

### Gate 4: Applications are submission-ready

Each permit has an auditable document checklist, human approval gate, reviewed snapshot, correction workflow and exportable Submission Readiness Package.

### Gate 5: The lifecycle is complete

Issued permits, inspections, final approvals and occupancy can all be tracked.

## Recommended implementation sequence

```text
Step 1: Intake and KCMO knowledge
        ↓
Step 2: Persistent permit records
        ↓
Step 3: Permit Bundle workspace
        ↓
First customer-facing MVP
        ↓
Step 4: Documents and corrections
        ↓
Step 5: Inspections and completion
```

Use live customer projects after Step 3 to validate and prioritize the document, correction and inspection workflows in Steps 4 and 5.
