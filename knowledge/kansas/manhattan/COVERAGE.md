# Manhattan, KS — Knowledge Pack Coverage

**Status: BULK INGEST — 266 MDC sections (Ch. 26 Arts 1–10)**

## Storage layout (project convention)

```
knowledge/
  {state}/
    state/                    ← state-wide (IBC adoption, etc.) — TODO
    {city}/
      metadata.json           ← sources, version, coverage
      zoning_rules.json       ← structured district thresholds
      site_development_rules.json  ← fences, parking, buffers
      fee_schedule.json
      permit_catalog.json
      environmental_triggers.json
      utility_requirements.json
      building_code_snippets/
      code_chunks/chunks.json ← RAG text with rule_id (expand over time)
```

## What IS included (as of 2026-06-19)

| Area | Coverage |
|------|----------|
| Zoning districts RL, RL-A, RM, RH, RC | Partial — key multifamily bulk tables |
| Infill development (Sec. 26-2C-5) | Yes |
| Permits & procedure types (Art. 26-8, 26-9) | Partial |
| Fee schedule (building, zoning, floodplain) | Yes |
| Fences & accessory structures (Sec. 26-7A-7) | **Added** |
| Buffer/screening fence heights (Sec. 26-7C) | Partial |
| RAG code chunks | **266 sections** (Arts 26-1–26-10) via `scripts/ingest_manhattan_code.py` |

## What is NOT included yet

The full MDC on [enCodePlus](https://online.encodeplus.com/regs/manhattan-udo) has **Chapter 26, Articles 26-1 through 26-10**, including:

- Article 26-1: Purpose and applicability
- Article 26-2D: Commercial & industrial districts (full tables)
- Article 26-3: Subdivision standards
- Article 26-4: Design standards (historic, urban core)
- Article 26-5: Thoroughfares, access management
- Article 26-6: Environmental / floodplain (full text)
- Article 26-7: Site development — **parking (26-7B), landscaping (26-7C), signs, lighting** — mostly not chunked yet
- Article 26-9: All land development review criteria in detail
- Article 26-10: Full definitions

**Hundreds of sections** — not scraped in full.

## How to get the rest

1. **Crawl script** — walk enCodePlus table of contents → one chunk per section → `code_chunks/`
2. **On-demand** — when user searches "fence height", RAG retrieves from chunks; missing topics → WARN
3. **Pilot-driven** — add sections Frontier Dev cares about first (infill, RM/RH, historic rehab)

## Official source of truth

Always: https://online.encodeplus.com/regs/manhattan-udo

This pack is a **grounding subset** for AI pre-screening, not a legal replacement for the full code.
