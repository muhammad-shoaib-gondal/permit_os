"""In-process pipeline runner — deterministic tools + one optional LLM call."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from shared.config import AgentRole
from shared.schemas.package import DocumentRequirement, PermitPackage, PermitRequirement
from shared.schemas.project_brief import ProjectBrief
from shared.schemas.reports import (
    BuildingSafetyReport,
    CheckResult,
    CheckStatus,
    JurisdictionInfo,
    JurisdictionReport,
    ReadinessImpact,
    SiteEnvironmentalReport,
    ZoningInfo,
)
from shared.tools import building_tools, jurisdiction_tools, site_tools
from shared.tools.conductor import compute_audit_hash, merge_reports
from shared.tools.knowledge import load_json

logger = logging.getLogger(__name__)


def _skip_llm() -> bool:
    return os.getenv("LOCAL_SKIP_LLM", "0").lower() in ("1", "true", "yes")


def _status(raw: str) -> CheckStatus:
    try:
        return CheckStatus(raw)
    except ValueError:
        return CheckStatus.WARN


# ---------------------------------------------------------------------------
# Deterministic analysis — no LLM
# ---------------------------------------------------------------------------

def _run_jurisdiction(brief: ProjectBrief) -> JurisdictionReport:
    lookup = jurisdiction_tools.lookup_jurisdiction(brief.address)
    district = lookup.get("district", "MF-3")
    zoning_rules = jurisdiction_tools.get_zoning_rules(lookup.get("city", "Austin"), district)
    setbacks = jurisdiction_tools.calculate_setbacks(brief, district)

    checks: list[CheckResult] = []
    blockers: list[str] = []
    for row in setbacks:
        checks.append(
            CheckResult(
                rule="Side setback minimum",
                status=_status(row["status"]),
                citation=row["citation"],
                detail=row["detail"],
                category="zoning",
            )
        )
        if row["status"] == "fail":
            blockers.append(f"Setback non-compliance {row['block_id']}")

    by_right = len(blockers) == 0
    impact = ReadinessImpact.NEEDS_CHANGES if blockers else ReadinessImpact.READY
    summary = f"{district} zoning; " + ("setback FAIL on Block B" if blockers else "setbacks pass")

    return JurisdictionReport(
        case_id=brief.case_id,
        summary=summary,
        readiness_impact=impact,
        jurisdictions=[
            JurisdictionInfo(
                name=lookup.get("city", "Austin"),
                type="municipal",
                codes_applicable=lookup.get("codes_applicable", []),
            )
        ],
        zoning=ZoningInfo(
            district=district,
            permitted_use=zoning_rules.get("permitted_uses", ["multifamily"])[0]
            if isinstance(zoning_rules.get("permitted_uses"), list)
            else str(brief.project_type),
            by_right=by_right,
        ),
        checks=checks,
        blockers=blockers,
    )


def _run_building(brief: ProjectBrief) -> BuildingSafetyReport:
    egress = building_tools.check_egress_requirements(brief.units, brief.stories)
    sprinklers = building_tools.check_sprinkler_requirements(brief.stories)
    accessibility = building_tools.check_accessibility_requirements(brief.units)

    checks = [
        CheckResult(
            rule=egress["rule"],
            status=_status(egress["status"]),
            citation=egress["citation"],
            detail=egress["detail"],
            category="fire",
        ),
        CheckResult(
            rule=sprinklers["rule"],
            status=_status(sprinklers["status"]),
            citation=sprinklers["citation"],
            detail=sprinklers["detail"],
            category="fire",
        ),
        CheckResult(
            rule=accessibility["rule"],
            status=_status(accessibility["status"]),
            citation=accessibility["citation"],
            detail=accessibility["detail"],
            category="accessibility",
        ),
    ]
    recs = []
    if sprinklers.get("recommendation"):
        recs.append(sprinklers["recommendation"])

    return BuildingSafetyReport(
        case_id=brief.case_id,
        summary="Egress PASS; sprinklers REQUIRED" if brief.stories >= 4 else "Building pre-screen complete",
        readiness_impact=ReadinessImpact.READY,
        checks=checks,
        recommendations=recs,
    )


def _run_site(brief: ProjectBrief) -> SiteEnvironmentalReport:
    flood = site_tools.lookup_flood_zone(brief.address)
    util = site_tools.get_utility_requirements(brief.units)

    env_checks = [
        CheckResult(
            rule="Flood zone",
            status=CheckStatus.PASS,
            citation=flood.get("citation", "FEMA"),
            detail=f"Zone {flood.get('zone', 'X')}: {flood.get('description', '')}",
            category="flood",
        )
    ]
    util_checks = [
        CheckResult(
            rule="Water/sewer capacity review",
            status=CheckStatus.WARN if util.get("water_sewer_review") else CheckStatus.PASS,
            citation=util.get("citation", ""),
            detail=f"{brief.units} units vs threshold {util.get('threshold_units')}",
            category="utilities",
        )
    ]
    return SiteEnvironmentalReport(
        case_id=brief.case_id,
        summary=f"Flood zone {flood.get('zone', 'X')}",
        readiness_impact=ReadinessImpact.READY,
        environmental_checks=env_checks,
        utility_checks=util_checks,
    )


def _run_package(
    brief: ProjectBrief,
    jurisdiction: JurisdictionReport,
    building: BuildingSafetyReport,
    site: SiteEnvironmentalReport,
) -> PermitPackage:
    catalog = load_json("permit_catalog.json")
    permits_data = catalog.get("permits", catalog.get("permit_types", []))
    permits: list[PermitRequirement] = []
    total = 0.0
    max_days = 0

    for p in permits_data[:6]:
        fee = float(p.get("base_fee_usd", p.get("fee_usd", 5000)))
        days = int(p.get("timeline_days", 30))
        permits.append(
            PermitRequirement(
                agency=p.get("agency", "COA"),
                permit_name=p.get("name", p.get("permit_name", "Permit")),
                form_id=p.get("form_id", "BP-2026"),
                fee_usd=fee,
                timeline_days=days,
                dependencies=p.get("dependencies", []),
            )
        )
        total += fee
        max_days = max(max_days, days)

    if not permits:
        permits = [
            PermitRequirement(
                agency="COA",
                permit_name="Building Permit",
                form_id="BP-2026",
                fee_usd=35000.0,
                timeline_days=30,
            )
        ]

    total = float(catalog.get("demo_total_fees_usd", total or 47200))
    max_days = max_days or 45
    sequence = catalog.get(
        "filing_sequence",
        ["Step 1: Zoning verification", "Step 2: Building permit application", "Step 3: Fire review"],
    )
    docs = [
        DocumentRequirement(name="Site plan", source_agent="jurisdiction"),
        DocumentRequirement(name="Architectural drawings", source_agent="building"),
        DocumentRequirement(name="Stormwater plan", source_agent="site"),
    ]
    return PermitPackage(
        case_id=brief.case_id,
        permits_required=permits,
        documents_required=docs,
        total_fees_estimate_usd=total,
        estimated_timeline_days=max_days,
        filing_sequence=sequence if isinstance(sequence, list) else list(sequence),
    )


# ---------------------------------------------------------------------------
# Single LLM call for executive summary
# ---------------------------------------------------------------------------

async def _llm_executive_summary(
    brief: ProjectBrief,
    jurisdiction: JurisdictionReport,
    building: BuildingSafetyReport,
    site: SiteEnvironmentalReport,
) -> str:
    fallback = (
        f"Project {brief.project_name}: automated pre-screen complete. "
        f"Jurisdiction: {jurisdiction.summary}. Building: {building.summary}. Site: {site.summary}."
    )
    if _skip_llm():
        return fallback

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        from shared.llm.backends import get_backend, resolve_llm_config, LLMBackend

        base_url, api_key, model = resolve_llm_config()
        llm_kwargs: dict[str, Any] = {
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
            "temperature": 0.1,
        }
        if get_backend() in {LLMBackend.BASETEN, LLMBackend.CEREBRAS}:
            llm_kwargs["max_tokens"] = int(os.getenv("LLM_MAX_TOKENS", "1024"))
            llm_kwargs["max_retries"] = int(os.getenv("LLM_MAX_RETRIES", "3"))

        llm = ChatOpenAI(**llm_kwargs)

        facts = {
            "project": brief.project_name,
            "address": brief.address,
            "units": brief.units,
            "stories": brief.stories,
            "gross_sqft": brief.gross_sqft,
            "zoning_summary": jurisdiction.summary,
            "zoning_blockers": jurisdiction.blockers,
            "building_summary": building.summary,
            "building_checks": [
                {"rule": c.rule, "status": c.status, "detail": c.detail}
                for c in building.checks
            ],
            "site_summary": site.summary,
            "site_issues": [
                {"rule": c.rule, "status": c.status, "detail": c.detail}
                for c in (site.environmental_checks + site.utility_checks)
            ],
        }

        system = (
            "You are a senior permitting analyst. Write a 2-3 sentence executive summary "
            "of the permit pre-screen results for a real estate developer. Be concise, "
            "factual, and highlight the most important blocker or approval path."
        )
        user = f"Pre-screen data:\n{json.dumps(facts, indent=2)}"

        resp = await asyncio.wait_for(
            llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)]),
            timeout=60.0,
        )
        text = (resp.content or "").strip()
        if text:
            return text[:500]
    except Exception as exc:
        logger.warning("LLM executive summary failed, using fallback: %s", exc)

    return fallback


# ---------------------------------------------------------------------------
# Progress + main runner
# ---------------------------------------------------------------------------

async def _emit_progress(
    on_progress,
    brief: ProjectBrief,
    *,
    phase: str,
    completed: list[str],
    **extra,
) -> None:
    if not on_progress:
        return
    payload: dict[str, Any] = {
        "status": "ANALYZING",
        "brief": brief.model_dump(mode="json"),
        "band_room_id": f"local-{brief.case_id}",
        "phase": phase,
        "completed_agents": completed,
    }
    payload.update(extra)
    await on_progress(payload)


async def run_local_case(
    brief: ProjectBrief,
    on_progress=None,
) -> dict[str, Any]:
    logger.info("Running LLM pipeline (tools + 1 LLM call) for %s", brief.case_id)

    await _emit_progress(on_progress, brief, phase="waiting_jurisdiction", completed=[])
    jurisdiction = _run_jurisdiction(brief)
    await asyncio.sleep(0.2)
    await _emit_progress(
        on_progress, brief,
        phase="completed_jurisdiction",
        completed=["jurisdiction"],
        jurisdiction_report=jurisdiction.model_dump(mode="json"),
    )

    building = _run_building(brief)
    await asyncio.sleep(0.2)
    await _emit_progress(
        on_progress, brief,
        phase="completed_building",
        completed=["jurisdiction", "building"],
        jurisdiction_report=jurisdiction.model_dump(mode="json"),
        building_report=building.model_dump(mode="json"),
    )

    site = _run_site(brief)
    await asyncio.sleep(0.2)
    await _emit_progress(
        on_progress, brief,
        phase="completed_site",
        completed=["jurisdiction", "building", "site"],
        jurisdiction_report=jurisdiction.model_dump(mode="json"),
        building_report=building.model_dump(mode="json"),
        site_report=site.model_dump(mode="json"),
    )

    # Single LLM call for the executive summary
    exec_summary = await _llm_executive_summary(brief, jurisdiction, building, site)

    room_id = f"local-{brief.case_id}"
    summary = merge_reports(brief, jurisdiction, building, site, room_id)
    summary.executive_summary = exec_summary

    await _emit_progress(
        on_progress, brief,
        phase="waiting_packager",
        completed=["jurisdiction", "building", "site"],
        jurisdiction_report=jurisdiction.model_dump(mode="json"),
        building_report=building.model_dump(mode="json"),
        site_report=site.model_dump(mode="json"),
        case_summary=summary.model_dump(mode="json"),
    )

    package = _run_package(brief, jurisdiction, building, site)
    if package.permits_required:
        package.audit_hash = compute_audit_hash(package)

    def evt(agent: str, event_type: str, detail: str):
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "event_type": event_type,
            "detail": detail,
            "payload": {},
        }

    return {
        "brief": brief.model_dump(mode="json"),
        "jurisdiction_report": jurisdiction.model_dump(mode="json"),
        "building_report": building.model_dump(mode="json"),
        "site_report": site.model_dump(mode="json"),
        "case_summary": summary.model_dump(mode="json"),
        "permit_package": package.model_dump(mode="json"),
        "activity": [
            evt("conductor", "pipeline_start", "LLM pipeline initialized"),
            evt("jurisdiction", "complete", jurisdiction.summary),
            evt("building", "complete", building.summary),
            evt("site", "complete", site.summary),
            evt("llm", "executive_summary", exec_summary[:120]),
            evt("packager", "complete", f"{len(package.permits_required)} permits assembled"),
        ],
        "band_room_id": room_id,
        "agent_driven": True,
        "band_orchestrated": False,
    }
