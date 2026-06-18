# PermitOS — Demo video script (~4 minutes)

Use this as a spoken walkthrough while screen-recording.  
**Before you hit record:** agents running, UI open, sample brief ready (`web/public/sample-project-brief.json`).

---

## 0:00 — Hook (15 sec)

> "Every real estate developer knows this pain: before you can break ground, you need a stack of permits — zoning, building, environmental — and one mistake means weeks of back-and-forth with the city.
>
> We built **PermitOS** — your multi-agent permitting team, powered by **Band of Agents**."

---

## 0:15 — Problem (20 sec)

> "Today, cities are adding AI on the *reviewer* side. Developers are still stuck in email, PDFs, and expensive consultants.
>
> PermitOS flips that: a governed team of specialist AI agents that *pre-screens* your project against real codes — with citations, conflict detection, and a full audit trail."

---

## 0:35 — Architecture (25 sec)

> "Here's how it works. A developer uploads a project brief — address, units, setbacks, plans.
>
> Our **Conductor** opens a Band chatroom and dispatches four specialists in sequence:
> **Jurisdiction & Zoning**, **Building & Safety**, **Site & Environmental**, and the **Permit Packager**.
>
> Each agent uses Austin tools and returns structured JSON. The Conductor merges everything into one readiness report."

*Optional: quick cut to Band chat showing @mentions — 5 seconds.*

---

## 1:00 — Live demo: intake (30 sec)

> "Let's run a real scenario: **Riverside Residences** — a 50-unit multifamily project in Austin."

**On screen:** Select jurisdiction **Austin**, project type **Multifamily**, drag in `sample-project-brief.json`.

> "The brief includes an intentional issue: Block B's east wall is at **8 feet**, but Austin requires **10 feet** on that side setback."

**Click Analyze.**

---

## 1:30 — Agents working (45 sec)

> "PermitOS is orchestrating live agents on Band — you can see the progress timer and each specialist filling in as they complete."

**On screen:** Point to the agent grid (jurisdiction → building → site).

> "Jurisdiction is checking zoning district, FAR, height, parking, density — each rule tied to a citation from the Austin Land Development Code."

*When jurisdiction appears:*

> "Five rules pass — but the **east side setback fails**. That's our blocker."

---

## 2:15 — Building & site (30 sec)

> "Building & Safety reviews life safety, fire access, ADA — independent from zoning."

> "Site & Environmental covers floodplain, stormwater, and utility capacity."

*Let them populate on screen.*

---

## 2:45 — Conductor summary + package (40 sec)

> "The Conductor merges all three reports. It flags the setback conflict and suggests a fix — move Block B or request a variance."

**Scroll to permit package:**

> "The Packager assembles what you'd actually file: required permits, fees, documents, and filing order — roughly **$47,000** and a **45-day** estimate for this scenario."

---

## 3:25 — Human gate + audit (25 sec)

**Click Approve.**

> "Nothing goes to the city without a human. Approval is logged with an **audit hash** — tamper-evident trace for regulated workflows."

**Click Simulate City RFI** (if shown):

> "If the city comes back with questions, PermitOS drafts a structured response from the case file."

---

## 3:50 — Close (20 sec)

> "PermitOS is Track 3 for **Band of Agents** — regulated, high-stakes workflows where you need multiple models, tool use, and human oversight.
>
> Multi-agent permitting, real citations, Band orchestration, developer-ready UI.
>
> Try it at **[your deployed URL]** — repo linked in the submission. Thanks."

---

## Recording tips

1. **One analysis only** — Baseten free tier is 15 requests/min; don't double-click Analyze.
2. **1920×1080**, hide desktop clutter, zoom browser to 110% if text is small.
3. **Mic check** — narrate *while* UI updates; pause 2–3 sec when waiting for agents.
4. **Backup take:** if Band is slow, show Band chat side-by-side with the dashboard.
5. **End card:** GitHub URL + hackathon track + your names.

---

## Short version (~90 sec) — social clip

> "Upload a project brief → four Band agents review zoning, building, and site → get a permit package with citations and fees → human approves with an audit trail. That's PermitOS."
