# Landing Page — Design & Handoff Notes

Context for work on the EstatePermit **marketing landing page**.
Last updated: **final v1** — single terracotta theme, redesign shipped & pushed; naming research added.

---

## 1. What this product is (quick context)

- **Product:** EstatePermit (marketed as **EstatePermit** on the landing page — name under review, see §8).
- **What it does:** A construction team creates a project, selects the work planned on site,
  and uploads the project files. EstatePermit identifies the applicable permits, loads the rules
  and document requirements for each permit, and uses LLM review to check the uploaded files.
  The final output is a cited, **submission-ready permit document bundle** with blockers and
  missing items clearly identified for human review.
- **Domain tone:** Regulated, high-stakes, B2B. Design should read **trustworthy, precise,
  premium** — not playful.
- **Disclaimer is mandatory** on the site: pre-screening only, not legal/engineering/architectural
  advice. Keep it in the footer.
- Product workflow: [`docs/EstatePermit_KCMO_Five_Step_Implementation_Plan.md`](./EstatePermit_KCMO_Five_Step_Implementation_Plan.md).
  Pricing rationale: [`contacts/PRICING.md`](../contacts/PRICING.md).
  Competitor research: [`contacts/COMPETITORS.md`](../contacts/COMPETITORS.md) +
  [`contacts/COMPETITORS_DEEP_DIVE.md`](../contacts/COMPETITORS_DEEP_DIVE.md).

---

## 2. Where the files live (IMPORTANT)

The live landing page is served from **`web/`**, not `landing/`.

| Live file (edit these) | Mirror (kept in sync) |
|------------------------|------------------------|
| `web/index.html` | `landing/index.html` |
| `web/public/css/styles.css` | `landing/css/styles.css` |
| `web/public/js/main.js` | `landing/js/main.js` |

- `landing/` is a **reference mirror**. After editing `web/`, copy the files into `landing/` so
  they don't drift (PowerShell `Copy-Item ... -Force`).
- `themes.css` was **deleted** in the finalize step (single theme now — see §4).
- `web/dist/` is **build output** from `npm run build` (run in `web/`). Don't hand-edit it; it
  regenerates. FastAPI serves `web/dist` in production when it exists, so **rebuild after changes**.
- The React product app (separate from the landing) is at `web/app/` and served at `/app`.

### Local dev
```bash
cd web && npm install && npm run dev
# Marketing: http://localhost:5173/    Product app: http://localhost:5173/app
```

---

## 3. Design system

- **Fonts:** `Fraunces` (display/headings, serif) + `DM Sans` (body). Loaded from Google Fonts.
- **All design tokens are CSS custom properties** in `styles.css` `:root` (single terracotta
  palette). Spacing/shape/shadows also live there.
- **Key tokens:** `--bg`, `--bg-elevated`, `--bg-subtle`, `--bg-dark`, `--bg-dark-soft`,
  `--text`, `--text-muted`, `--text-on-dark`, `--accent` (`#c45c26`), `--accent-hover`,
  `--accent-2` (gradient companion), `--accent-soft`, `--success/-soft`, `--warn/-soft`,
  `--danger/-soft`, `--radius*`, `--shadow*`.
- **Conventions:** add `.reveal` to fade-in on scroll (JS handles it). `.section--alt` = subtle
  alternate background. `.section-head(.center)` wraps label/title/lead. Buttons: `.btn` +
  `.btn-primary` / `.btn-secondary` / `.btn-ghost-light`, plus `.btn-lg`.

### Design highlights (vs the original landing)
- Warm **terracotta** palette (accent `#c45c26`), gradient-mesh hero, pill eyebrow, accent span on H1.
- Hero email form is **inline** (input + button), stacks on mobile; inline confirmation on submit.
- **Stats strip** under the hero (applicable permits / rule review / submission bundle / cited findings).
- Cards (value/steps/features/audience) have hover lift + softer shadows.
- FAQ = bordered cards, keyboard/AX accessible (`aria-expanded`, single-open).
- No inline `style=` colors in sections; sticky header border on scroll; `scroll-margin-top` anchors.
- Favicon (inline SVG, terracotta), Open Graph + Twitter meta tags.
- "Sign in" → `/app/?signin=1`; "Launch app" → `/app/`.
- Respects `prefers-reduced-motion`.

---

## 4. Theme / color (FINALIZED — single theme)

There is now **one** baked-in palette: **Terracotta** (accent `#c45c26`), in `styles.css` `:root`.
The earlier multi-theme experiment (indigo/slate/forest/teal/graphite) and the `?theme=` switcher
were **removed** per user request: `themes.css` deleted, its `<link>` removed, theme-switch JS
removed. To rebrand colors, edit the token values in `:root` directly.

---

## 5. Page structure (sections in order)

`header` → `hero` → `stat-strip` → `#value` (dark strip) → `#how` (steps) →
`#fit` (before/after) → `#features` (alt bg) → `#audience` (dark cards) →
`#pricing` (alt bg, placeholder) → `#faq` → CTA panel → `footer`.

### `#fit` — Before / after comparison
Competitor-informed. The product's wedge = a developer-facing pre-screen between code-research
tools (UpCodes) and full filing services (PermitFlow / GreenLite). Communicated as a **Before vs
After transformation** (not a workflow spectrum — that earlier version didn't land):
- `.compare-card--before` (muted bg, red ✕ list) = the old manual, rule-by-rule way.
- `.compare-card--after` (white, accent ring + shadow, green ✓ list, accent pill tag) = EstatePermit.
- Arrow (`.compare-arrow`) between; stacks vertically with a rotated arrow on mobile.
Message: "stop checking the code rule by rule — every applicable rule checked at once."
Do NOT position against PermitFlow on full filing or GreenLite on licensed/stamped review (out of scope).

### `#pricing` — placeholder
Price tiers ($79/$199/Custom) were **removed**; section now shows a simple "talk to us about
pricing" block (`.pricing-simple`). The old `.price-card` CSS was also deleted. Internal pricing
rationale lives in `contacts/PRICING.md`.

---

## 5b. Hero app-video slot (TODO for later)
The hero right column (`.hero-visual`) shows the static "Riverside Residences" mock card. The user
wants a **product/animation demo video** there eventually. There's an HTML comment in
`web/index.html` marking the swap point, and a ready `.hero-video` style in `styles.css`. To go
live: drop a `<video>` (autoplay/muted/loop/playsinline + poster) in place of `.mock-card`, add the
asset under `web/public/`, mirror to `landing/`.

---

## 6. Git / shipping state
- Branch: **`feature/estatepermit-landing-page`** (tracks `origin`,
  github.com/muhammad-shoaib-gondal/permit_os).
- Redesign committed & pushed as `1d207c0` — **only the 8 landing-page files** (web + landing
  mirror). Deliberately NOT committed: `.gitignore`, `web/tsconfig.node.tsbuildinfo`,
  `knowledge/kansas/`, `scripts/ingest_manhattan_code.py`, and this doc.
- Cache-buster is `?v=final` on `styles.css` in `index.html` — bump it when shipping CSS changes.
- Rebuild `web/dist` (`npm run build`) for production to reflect changes.

---

## 7. Open suggestions / not yet done
- Footer **Privacy / Terms** links are still `href="#"` (no pages yet).
- Email form is **mailto-based** (no backend capture). Wire to a real waitlist endpoint later.
- No real OG **image** yet (only text tags). Add `og:image` when a brand image exists.
- App demo video for the hero (see §5b).

---

## 8. Name research (Jun 2026)

User wants a broader name than "EstatePermit" (permits are only part of the product). Considered
"Estate Intel", "LandIntel", "scans/lens" variants, etc. **Findings from web search** (must still
be verified on a registrar + USPTO TESS before adopting — search is not legal clearance):

| Candidate | Status | Notes |
|-----------|--------|-------|
| **EstatePermit** | ✅ clearest | No direct company found on the exact name. Already built into this site. Downside: "permit" reads narrow. |
| Estate Intel | ❌ taken | `estateintel.com` — funded African real-estate **data/intelligence** co (since 2014, US presence). Same category. |
| LandIntel | ❌ taken ×2 | `landintel.com.au` ("know what you can build before you commit" = our pitch) + `landintel.io` (land-investment SaaS). |
| Zonely | ❌ taken ×3 | golf (AU), SA real-estate zoning, US app. |
| ZoneWise | ❌ taken | `getzonewise.com` + `zonewise.ai` (FL zoning/foreclosure AI). |
| ParcelIQ | ❌ taken ×3+ | `parceliqpro.com` does zoning/dev analysis; also investment + logistics uses. |
| PreDev / PreDevelopment | ❌ taken | `predev.com.au` (town planning) + `predevelopment.ai` (CA due diligence). |
| Lintel | ❌ taken ×5+ | incl. `uselintel.com` construction-doc AI. |
| Permio | ⚠️ defunct | `permio.ai` construction-permit AI **ceased ops Oct 2025**. Possibly acquirable but tainted. |
| PermitWise / Permify | ❌ taken | restaurant permit tracker / authz (acquired by FusionAuth). |

**Also already in the space:** PermitFlow, GreenLite, UpCodes, Symbium, Anori, GovWell, Govstream,
CodeComply, CivCheck, PermitPortal (YC), CivitPERMIT, Permitium, Permitify, permittable.ai,
AutoSitu, ReadyPermit/Buildability, Spacio, PreDevelopment AI.

### Recommendation
1. The **descriptive** naming space (zoning/parcel/permit + IQ/wise/intel/scan) is essentially
   saturated, often by direct competitors. Don't expect a clean descriptive .com.
2. **Keep EstatePermit** unless rebranding is a priority — it's one of the few clear, ownable names
   and is already built here.
3. If broadening the name, go **coined / abstract** (not descriptive) for a real shot at a clear
   trademark + domain. Verify any final pick on a registrar (.com) **and** USPTO TESS, classes 9/42
   (software) and 36 (real estate).
