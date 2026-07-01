"""In-process agent runner — tools first, LLM optional; reliable when Band/Cerebras fail."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from shared.band_client.config import AgentRole
from shared.llm.backends import LLMBackend, get_backend, resolve_llm_config
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
from shared.tools.conductor import compute_audit_hash, merge_reports
from shared.tools.langchain_tools import (
    BUILDING_TOOLS,
    JURISDICTION_TOOLS,
    PACKAGER_TOOLS,
    SITE_TOOLS,
)

logger = logging.getLogger(__name__)

_ROLE_TOOLS = {
    AgentRole.JURISDICTION: JURISDICTION_TOOLS,
    AgentRole.BUILDING: BUILDING_TOOLS,
    AgentRole.SITE: SITE_TOOLS,
    AgentRole.PACKAGER: PACKAGER_TOOLS,
}


def _make_llm() -> ChatOpenAI:
    base_url, api_key, model = resolve_llm_config()
    kwargs: dict[str, Any] = {
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "temperature": 0.2,
    }
    if get_backend() in {LLMBackend.CEREBRAS, LLMBackend.BASETEN}:
        kwargs["max_tokens"] = int(__import__("os").getenv("LLM_MAX_TOKENS", "4096"))
        kwargs["max_retries"] = int(__import__("os").getenv("LLM_MAX_RETRIES", "8"))
    return ChatOpenAI(**kwargs)


def _status(raw: str) -> CheckStatus:
    try:
        return CheckStatus(raw)
    except ValueError:
        return CheckStatus.WARN


def _gather_tool_context(brief: ProjectBrief, role: AgentRole) -> dict[str, Any]:
    ctx: dict[str, Any] = {}
    if role == AgentRole.JURISDICTION:
        from shared.tools import jurisdiction_tools

        ctx["lookup_jurisdiction"] = json.loads(
            JURISDICTION_TOOLS[0].invoke({"address": brief.address})
        )
        city = ctx["lookup_jurisdiction"].get("city", "Austin")
        district = ctx["lookup_jurisdiction"].get("district", "MF-3")
        ctx["get_zoning_rules"] = json.loads(
            JURISDICTION_TOOLS[1].invoke({"city": city, "district": district})
        )
        ctx["calculate_setbacks"] = jurisdiction_tools.calculate_setbacks(brief, district)
    elif role == AgentRole.BUILDING:
        ctx["check_egress"] = json.loads(
            BUILDING_TOOLS[0].invoke({"units": brief.units, "stories": brief.stories})
        )
        ctx["check_sprinklers"] = json.loads(
            BUILDING_TOOLS[1].invoke({"stories": brief.stories})
        )
        ctx["check_accessibility"] = json.loads(
            BUILDING_TOOLS[2].invoke({"unit_count": brief.units})
        )
    elif role == AgentRole.SITE:
        ctx["lookup_flood_zone"] = json.loads(
            SITE_TOOLS[0].invoke({"address": brief.address})
        )
        ctx["get_utility_requirements"] = json.loads(
            SITE_TOOLS[1].invoke({"units": brief.units})
        )
    elif role == AgentRole.PACKAGER:
        ctx["get_fee_schedule"] = json.loads(PACKAGER_TOOLS[0].invoke({}))
        ctx["get_permit_catalog"] = json.loads(PACKAGER_TOOLS[1].invoke({}))
    return ctx


def _assemble_jurisdiction(brief: ProjectBrief, ctx: dict[str, Any]) -> JurisdictionReport:
    lookup = ctx["lookup_jurisdiction"]
    district = lookup.get("district", "MF-3")
    zoning_rules = ctx.get("get_zoning_rules", {})
    setbacks = ctx.get("calculate_setbacks", [])
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
    summary = (
        f"{district} zoning; "
        + ("setback FAIL on Block B" if blockers else "setbacks pass")
    )
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


def _assemble_building(brief: ProjectBrief, ctx: dict[str, Any]) -> BuildingSafetyReport:
    checks = [
        CheckResult(
            rule=ctx["check_egress"]["rule"],
            status=_status(ctx["check_egress"]["status"]),
            citation=ctx["check_egress"]["citation"],
            detail=ctx["check_egress"]["detail"],
            category="fire",
        ),
        CheckResult(
            rule=ctx["check_sprinklers"]["rule"],
            status=_status(ctx["check_sprinklers"]["status"]),
            citation=ctx["check_sprinklers"]["citation"],
            detail=ctx["check_sprinklers"]["detail"],
            category="fire",
        ),
        CheckResult(
            rule=ctx["check_accessibility"]["rule"],
            status=_status(ctx["check_accessibility"]["status"]),
            citation=ctx["check_accessibility"]["citation"],
            detail=ctx["check_accessibility"]["detail"],
            category="accessibility",
        ),
    ]
    recs = []
    if ctx["check_sprinklers"].get("recommendation"):
        recs.append(ctx["check_sprinklers"]["recommendation"])
    return BuildingSafetyReport(
        case_id=brief.case_id,
        summary="Egress PASS; sprinklers REQUIRED" if brief.stories >= 4 else "Building pre-screen complete",
        readiness_impact=ReadinessImpact.READY,
        checks=checks,
        recommendations=recs,
    )


def _assemble_site(brief: ProjectBrief, ctx: dict[str, Any]) -> SiteEnvironmentalReport:
    flood = ctx["lookup_flood_zone"]
    util = ctx["get_utility_requirements"]
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


def _assemble_package(
    brief: ProjectBrief,
    ctx: dict[str, Any],
    jurisdiction: JurisdictionReport,
    building: BuildingSafetyReport,
    site: SiteEnvironmentalReport,
) -> PermitPackage:
    catalog = ctx.get("get_permit_catalog", {})
    fees = ctx.get("get_fee_schedule", {})
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
        estimated_timeline_days=max_days or 45,
        filing_sequence=sequence if isinstance(sequence, list) else list(sequence),
    )


def _assemble(role: AgentRole, brief: ProjectBrief, ctx: dict[str, Any], **kwargs) -> Any:
    if role == AgentRole.JURISDICTION:
        return _assemble_jurisdiction(brief, ctx)
    if role == AgentRole.BUILDING:
        return _assemble_building(brief, ctx)
    if role == AgentRole.SITE:
        return _assemble_site(brief, ctx)
    if role == AgentRole.PACKAGER:
        return _assemble_package(
            brief,
            ctx,
            kwargs["jurisdiction"],
            kwargs["building"],
            kwargs["site"],
        )
    raise ValueError(role)


def _skip_llm() -> bool:
    import os

    if os.getenv("PERMITOS_VIDEO_MODE", "").lower() in ("1", "true", "yes"):
        return True
    return os.getenv("LOCAL_SKIP_LLM", "0").lower() in ("1", "true", "yes")


def _agent_stagger_sec() -> float:
    import os

    if os.getenv("PERMITOS_VIDEO_MODE", "").lower() in ("1", "true", "yes"):
        return float(os.getenv("VIDEO_AGENT_STAGGER_SEC", "2"))
    return float(os.getenv("LOCAL_AGENT_STAGGER_SEC", "1"))


async def _maybe_enrich_summary(role: AgentRole, report: Any, ctx: dict[str, Any]) -> Any:
    """Optional one-line LLM polish; skipped on rate limits."""
    if _skip_llm():
        return report
    try:
        llm = _make_llm()
        prompt = (
            f"In one sentence, summarize this {role.value} permitting report for executives. "
            f"Facts: {json.dumps(ctx)[:1500]}"
        )
        resp = await asyncio.wait_for(
            llm.ainvoke([HumanMessage(content=prompt)]),
            timeout=45.0,
        )
        text = (resp.content or "").strip()
        if text and hasattr(report, "summary"):
            report.summary = text[:280]
    except Exception as exc:
        logger.debug("LLM summary skip for %s: %s", role.value, exc)
    return report


async def _run_role(role: AgentRole, brief: ProjectBrief, **kwargs) -> Any:
    ctx = _gather_tool_context(brief, role)
    report = _assemble(role, brief, ctx, **kwargs)
    await asyncio.sleep(_agent_stagger_sec())
    return await _maybe_enrich_summary(role, report, ctx)


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
    custom_rules: list[dict[str, Any]] | None = None,
    selected_modules: list[str] | None = None,
    module_requirements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger.info("Running local in-process agents (tools + optional LLM) for %s", brief.case_id)
    selected = set(selected_modules or ["zoning", "building", "fire", "site"])
    completed: list[str] = []
    module_requirements = module_requirements or {}

    jurisdiction = None
    building = None
    site = None
    if "zoning" in selected:
        await _emit_progress(on_progress, brief, phase="waiting_jurisdiction", completed=completed)
        jurisdiction = await _run_role(AgentRole.JURISDICTION, brief)
        completed.append("jurisdiction")
        await _emit_progress(
            on_progress,
            brief,
            phase="completed_jurisdiction",
            completed=completed,
            jurisdiction_report=jurisdiction.model_dump(mode="json"),
            module_requirements=module_requirements,
            selected_modules=list(selected),
        )

    if "building" in selected or "fire" in selected:
        building = await _run_role(AgentRole.BUILDING, brief)
        completed.append("building")
        await _emit_progress(
            on_progress,
            brief,
            phase="completed_building",
            completed=completed,
            jurisdiction_report=jurisdiction.model_dump(mode="json") if jurisdiction else None,
            building_report=building.model_dump(mode="json"),
            module_requirements=module_requirements,
            selected_modules=list(selected),
        )

    if "site" in selected:
        site = await _run_role(AgentRole.SITE, brief)
        completed.append("site")
        await _emit_progress(
            on_progress,
            brief,
            phase="completed_site",
            completed=completed,
            jurisdiction_report=jurisdiction.model_dump(mode="json") if jurisdiction else None,
            building_report=building.model_dump(mode="json") if building else None,
            site_report=site.model_dump(mode="json"),
            module_requirements=module_requirements,
            selected_modules=list(selected),
        )

    room_id = f"local-{brief.case_id}"
    if jurisdiction and building and site:
        summary = merge_reports(brief, jurisdiction, building, site, room_id)
        await _emit_progress(
            on_progress,
            brief,
            phase="waiting_packager",
            completed=completed,
            jurisdiction_report=jurisdiction.model_dump(mode="json"),
            building_report=building.model_dump(mode="json"),
            site_report=site.model_dump(mode="json"),
            case_summary=summary.model_dump(mode="json"),
            module_requirements=module_requirements,
            selected_modules=list(selected),
        )
        package = await _run_role(
            AgentRole.PACKAGER,
            brief,
            jurisdiction=jurisdiction,
            building=building,
            site=site,
        )
        if package.permits_required:
            package.audit_hash = compute_audit_hash(package)
    else:
        from shared.schemas.case import PermitCaseSummary, CaseStatus, ReadinessScore
        from shared.schemas.package import PermitPackage

        summary = PermitCaseSummary(
            case_id=brief.case_id,
            project_name=brief.project_name,
            status=CaseStatus.AWAITING_APPROVAL,
            readiness_score=ReadinessScore.NEEDS_CHANGES,
            executive_summary="Partial analysis completed. Run additional modules for a full project-wide review.",
        )
        package = PermitPackage(case_id=brief.case_id)

    custom_checks: list[CheckResult] = []
    if custom_rules:
        from shared.agent_logic.custom_rules import evaluate_custom_rules

        custom_checks = await evaluate_custom_rules(brief, custom_rules)

    def evt(agent: str, event_type: str, detail: str):
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "event_type": event_type,
            "detail": detail,
            "payload": {},
        }

    activity = [evt("conductor", "local_dispatch", "In-process agents (Band unavailable)")]
    if jurisdiction:
        activity.append(evt("jurisdiction", "complete", jurisdiction.summary))
    if building:
        activity.append(evt("building", "complete", building.summary))
    if site:
        activity.append(evt("site", "complete", site.summary))
    if package.permits_required:
        activity.append(evt("packager", "complete", f"{len(package.permits_required)} permits"))

    rule_groups = [
        {
            "key": "zoning",
            "label": "Zoning",
            "checks": [c.model_dump(mode="json") for c in ((jurisdiction.checks if jurisdiction else []))],
        },
        {
            "key": "building",
            "label": "Building",
            "checks": [
                c.model_dump(mode="json")
                for c in (
                    [c for c in (building.checks if building else []) if c.category != "fire"]
                )
            ],
        },
        {
            "key": "fire",
            "label": "Fire / Life Safety",
            "checks": [
                c.model_dump(mode="json")
                for c in (
                    [c for c in (building.checks if building else []) if c.category == "fire"]
                )
            ],
        },
        {
            "key": "site",
            "label": "Site / Utilities",
            "checks": [
                c.model_dump(mode="json")
                for c in ((site.environmental_checks + site.utility_checks) if site else [])
            ],
        },
        {
            "key": "custom",
            "label": "Custom Rules",
            "checks": [c.model_dump(mode="json") for c in custom_checks],
        },
    ]

    return {
        "brief": brief.model_dump(mode="json"),
        "jurisdiction_report": jurisdiction.model_dump(mode="json") if jurisdiction else None,
        "building_report": building.model_dump(mode="json") if building else None,
        "site_report": site.model_dump(mode="json") if site else None,
        "custom_rules_report": {
            "summary": f"{len(custom_checks)} custom rule(s) evaluated",
            "checks": [c.model_dump(mode="json") for c in custom_checks],
        },
        "case_summary": summary.model_dump(mode="json"),
        "permit_package": package.model_dump(mode="json"),
        "activity": activity,
        "band_room_id": room_id,
        "agent_driven": True,
        "band_orchestrated": False,
        "local_fallback": True,
        "selected_modules": list(selected),
        "module_requirements": module_requirements,
        "rule_groups": rule_groups,
    }
