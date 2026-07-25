"""In-process analysis runner using deterministic tools and required ZenMux review."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from langchain_core.messages import HumanMessage
from shared.llm.zenmux import create_chat_model
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
from shared.tools.analysis_summary import compute_audit_hash, merge_reports
from shared.tools.kcmo_permits import match_kcmo_applications
from shared.tools.kck_permits import match_kck_applications
from shared.tools.lenexa_permits import match_lenexa_applications
from shared.tools.overland_park_permits import match_overland_park_applications
from shared.tools.langchain_tools import (
    BUILDING_TOOLS,
    JURISDICTION_TOOLS,
    PACKAGER_TOOLS,
    SITE_TOOLS,
)

logger = logging.getLogger(__name__)

SUPPORTED_PERMIT_JURISDICTIONS = {
    "kansas_city_mo": "Kansas City, Missouri",
    "kansas_city_ks": "Kansas City, Kansas",
    "lenexa_ks": "Lenexa, Kansas",
    "overland_park_ks": "Overland Park, Kansas",
}

class AnalysisSection(str, Enum):
    JURISDICTION = "jurisdiction"
    BUILDING = "building"
    SITE = "site"
    PACKAGING = "packaging"


def _make_llm():
    return create_chat_model()


def _status(raw: str) -> CheckStatus:
    try:
        return CheckStatus(raw)
    except ValueError:
        return CheckStatus.WARN


def _gather_tool_context(brief: ProjectBrief, section: AnalysisSection) -> dict[str, Any]:
    ctx: dict[str, Any] = {}
    if section == AnalysisSection.JURISDICTION:
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
    elif section == AnalysisSection.BUILDING:
        ctx["check_egress"] = json.loads(
            BUILDING_TOOLS[0].invoke({"units": brief.units, "stories": brief.stories})
        )
        ctx["check_sprinklers"] = json.loads(
            BUILDING_TOOLS[1].invoke({"stories": brief.stories})
        )
        ctx["check_accessibility"] = json.loads(
            BUILDING_TOOLS[2].invoke({"unit_count": brief.units})
        )
    elif section == AnalysisSection.SITE:
        ctx["lookup_flood_zone"] = json.loads(
            SITE_TOOLS[0].invoke({"address": brief.address})
        )
        ctx["get_utility_requirements"] = json.loads(
            SITE_TOOLS[1].invoke({"units": brief.units})
        )
    elif section == AnalysisSection.PACKAGING:
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


def _assemble_supported_report(
    section: AnalysisSection,
    brief: ProjectBrief,
    authoritative_context: dict[str, Any] | None,
) -> JurisdictionReport | BuildingSafetyReport | SiteEnvironmentalReport:
    city_name = SUPPORTED_PERMIT_JURISDICTIONS[brief.jurisdiction]
    context = authoritative_context or {}
    profile = context.get("zoningProfile") if isinstance(context.get("zoningProfile"), dict) else {}
    district = str(profile.get("classification") or profile.get("district") or "").strip()
    if section == AnalysisSection.JURISDICTION:
        return JurisdictionReport(
            case_id=brief.case_id,
            summary="Permit-specific jurisdiction checks are reported in the review results.",
            readiness_impact=ReadinessImpact.NEEDS_CHANGES,
            jurisdictions=[JurisdictionInfo(name=city_name, type="municipal")],
            zoning=ZoningInfo(
                district=district,
                permitted_use=str(brief.use_description or brief.project_type.value),
                by_right=False,
            ) if district else None,
            data_gaps=[] if district else ["A verified zoning district was not available."],
        )
    if section == AnalysisSection.BUILDING:
        return BuildingSafetyReport(
            case_id=brief.case_id,
            summary="Permit-specific building and fire checks are reported in the review results.",
            readiness_impact=ReadinessImpact.NEEDS_CHANGES,
        )
    return SiteEnvironmentalReport(
        case_id=brief.case_id,
        summary="Permit-specific site and utility checks are reported in the review results.",
        readiness_impact=ReadinessImpact.NEEDS_CHANGES,
    )


def _assemble_package(
    brief: ProjectBrief,
    ctx: dict[str, Any],
    jurisdiction: JurisdictionReport,
    building: BuildingSafetyReport,
    site: SiteEnvironmentalReport,
    authoritative_context: dict[str, Any] | None = None,
    target_permit_types: list[str] | None = None,
) -> PermitPackage:
    if brief.jurisdiction in SUPPORTED_PERMIT_JURISDICTIONS:
        context = authoritative_context or {}
        target_set = set(target_permit_types or [])
        project_permits = [
            permit
            for permit in context.get("projectPermits", [])
            if permit.get("requirementStatus") == "required"
            and (not target_set or permit.get("permitType") in target_set)
        ]
        permits = [
            PermitRequirement(
                agency=str(
                    permit.get("issuingAuthority")
                    or SUPPORTED_PERMIT_JURISDICTIONS[brief.jurisdiction]
                ),
                permit_name=str(permit.get("permitName") or permit.get("permitType") or "Permit"),
                form_id=str(permit.get("permitType") or "permit"),
                fee_usd=float(permit.get("estimatedFeeUsd") or 0),
                timeline_days=0,
                dependencies=[str(value) for value in (permit.get("dependencies") or [])],
            )
            for permit in project_permits
        ]
        documents: list[DocumentRequirement] = []
        seen_documents: set[tuple[str, str]] = set()
        for permit in project_permits:
            permit_type = str(permit.get("permitType") or "permit")
            for document in permit.get("requiredDocuments") or []:
                name = str(document.get("name") if isinstance(document, dict) else document).strip()
                key = (permit_type, name.casefold())
                if not name or key in seen_documents:
                    continue
                seen_documents.add(key)
                documents.append(DocumentRequirement(name=name, source_section=permit_type))
        return PermitPackage(
            case_id=brief.case_id,
            permits_required=permits,
            documents_required=documents,
            total_fees_estimate_usd=sum(permit.fee_usd for permit in permits),
            estimated_timeline_days=0,
            filing_sequence=[permit.permit_name for permit in permits],
        )

    catalog = ctx.get("get_permit_catalog", {})
    permits_data = catalog.get("permits", catalog.get("permit_types", []))
    permits: list[PermitRequirement] = []
    total = 0.0
    max_days = 0
    if brief.jurisdiction == "kansas_city_mo":
        matched = match_kcmo_applications(
            _scope_from_brief(brief),
            brief.project_type.value,
            {
                "fire_alarm": brief.fire_alarm_work,
                "formal_trade_plans_required": bool(brief.plan_pdf_url),
            },
        )
        permits_data = [
            {
                "agency": "Kansas City, Missouri",
                "permit_name": item["name"],
                "form_id": f"COMPASS-{item['application_kind'].upper()}-{item['id']}",
                "fee_usd": 0,
                "timeline_days": 0,
                "dependencies": [],
            }
            for item in matched
            if item["requirement_status"] == "required"
        ]
    elif brief.jurisdiction == "kansas_city_ks":
        matched = match_kck_applications(_scope_from_brief(brief), brief.project_type.value)
        permits_data = [
            {
                "agency": item["authority"],
                "permit_name": item["name"],
                "form_id": f"KCK-{item['id'].upper()}",
                "fee_usd": 0,
                "timeline_days": 0,
                "dependencies": [],
            }
            for item in matched
            if item["requirement_status"] == "required"
        ]
    elif brief.jurisdiction in {"lenexa_ks", "overland_park_ks"}:
        matcher = match_lenexa_applications if brief.jurisdiction == "lenexa_ks" else match_overland_park_applications
        prefix = "LENEXA" if brief.jurisdiction == "lenexa_ks" else "OVERLAND-PARK"
        matched = matcher(_scope_from_brief(brief), brief.project_type.value)
        permits_data = [
            {
                "agency": item["authority"], "permit_name": item["name"],
                "form_id": f"{prefix}-{item['id'].upper()}", "fee_usd": 0,
                "timeline_days": 0, "dependencies": [],
            }
            for item in matched if item["requirement_status"] == "required"
        ]
    for p in permits_data:
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
    if not permits and brief.jurisdiction not in {"kansas_city_mo", "kansas_city_ks"}:
        permits = [
            PermitRequirement(
                agency="COA",
                permit_name="Building Permit",
                form_id="BP-2026",
                fee_usd=35000.0,
                timeline_days=30,
            )
        ]
    if brief.jurisdiction in {"kansas_city_mo", "kansas_city_ks"}:
        total = float(total)
    else:
        total = float(catalog.get("demo_total_fees_usd", total or 47200))
        max_days = max_days or 45

    sequence = catalog.get(
        "filing_sequence",
        ["Step 1: Zoning verification", "Step 2: Building permit application", "Step 3: Fire review"],
    )
    docs = [
        DocumentRequirement(name="Site plan", source_section="jurisdiction"),
        DocumentRequirement(name="Architectural drawings", source_section="building"),
        DocumentRequirement(name="Stormwater plan", source_section="site"),
    ]
    return PermitPackage(
        case_id=brief.case_id,
        permits_required=permits,
        documents_required=docs,
        total_fees_estimate_usd=total,
        estimated_timeline_days=max_days,
        filing_sequence=sequence if isinstance(sequence, list) else list(sequence),
    )


def _scope_from_brief(brief: ProjectBrief) -> dict[str, bool]:
    trades = {trade.casefold() for trade in brief.trade_scopes}
    scope_text = (brief.scope_of_work or "").casefold()
    return {
        "new_construction": "new construction" in scope_text,
        "addition": "addition" in scope_text,
        "alteration": any(term in scope_text for term in ("alteration", "remodel", "renovation", "tenant finish")),
        "repair": "repair" in scope_text,
        "demolition": any(term in scope_text for term in ("demolition", "demo")),
        "structural_work": "structural" in trades or "structural" in scope_text,
        "electrical_work": "electrical" in trades,
        "plumbing_work": "plumbing" in trades,
        "mechanical_hvac_work": bool(trades.intersection({"mechanical", "hvac", "kitchen_hood"})),
        "fire_alarm_sprinkler_work": brief.fire_alarm_work or brief.sprinkler_work,
        "signs": "sign" in trades or "signage" in scope_text,
        "change_use_occupancy": brief.change_of_use,
        "grading_land_disturbance": bool(trades.intersection({"grading", "land_disturbance"})),
        "driveway_sidewalk_row": brief.right_of_way_impacts,
        "solar_battery_generator_ev": bool(trades.intersection({"solar", "battery", "generator", "ev"})),
        "water_sewer_connections": bool(trades.intersection({"water", "sewer", "utility"})),
    }


def _assemble(section: AnalysisSection, brief: ProjectBrief, ctx: dict[str, Any], **kwargs) -> Any:
    if section == AnalysisSection.JURISDICTION:
        return _assemble_jurisdiction(brief, ctx)
    if section == AnalysisSection.BUILDING:
        return _assemble_building(brief, ctx)
    if section == AnalysisSection.SITE:
        return _assemble_site(brief, ctx)
    if section == AnalysisSection.PACKAGING:
        return _assemble_package(
            brief,
            ctx,
            kwargs["jurisdiction"],
            kwargs["building"],
            kwargs["site"],
            authoritative_context=kwargs.get("authoritative_context"),
            target_permit_types=kwargs.get("target_permit_types"),
        )
    raise ValueError(section)


async def _enrich_summary(
    section: AnalysisSection,
    report: Any,
    ctx: dict[str, Any],
    document_context: list[dict[str, Any]],
) -> Any:
    """Require ZenMux to review each analysis section."""
    llm = _make_llm()
    prompt = (
        f"Review these deterministic {section.value} permitting findings. In one sentence, "
        "summarize the result without inventing facts. Use the uploaded-document summaries as "
        "evidence, and clearly state when they do not contain a value needed for the finding. "
        f"Deterministic facts: {json.dumps(ctx)[:3000]}. "
        f"Uploaded documents: {json.dumps(document_context)[:6000]}"
    )
    resp = await asyncio.wait_for(
        llm.ainvoke([HumanMessage(content=prompt)]),
        timeout=180.0,
    )
    text = str(resp.content or "").strip()
    if text and hasattr(report, "summary"):
        report.summary = text[:280]
    return report


async def _run_section(
    section: AnalysisSection,
    brief: ProjectBrief,
    document_context: list[dict[str, Any]],
    **kwargs,
) -> Any:
    if brief.jurisdiction in SUPPORTED_PERMIT_JURISDICTIONS:
        if section == AnalysisSection.PACKAGING:
            return _assemble(
                section,
                brief,
                {},
                jurisdiction=kwargs["jurisdiction"],
                building=kwargs["building"],
                site=kwargs["site"],
                authoritative_context=kwargs.get("authoritative_context"),
                target_permit_types=kwargs.get("target_permit_types"),
            )
        return _assemble_supported_report(section, brief, kwargs.get("authoritative_context"))
    ctx = _gather_tool_context(brief, section)
    report = _assemble(section, brief, ctx, **kwargs)
    return await _enrich_summary(section, report, ctx, document_context)


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
        "phase": phase,
        "completed_sections": completed,
    }
    payload.update(extra)
    await on_progress(payload)


async def run_analysis(
    brief: ProjectBrief,
    on_progress=None,
    custom_rules: list[dict[str, Any]] | None = None,
    selected_modules: list[str] | None = None,
    module_requirements: dict[str, Any] | None = None,
    document_context: list[dict[str, Any]] | None = None,
    target_permit_types: list[str] | None = None,
    authoritative_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger.info("Running local tools with required ZenMux review for %s", brief.case_id)
    selected = set(selected_modules or ["zoning", "building", "fire", "site"])
    completed: list[str] = []
    module_requirements = module_requirements or {}
    document_context = document_context or []
    target_permit_types = target_permit_types or []
    review_document_context = [
        {"review_scope": {"permit_types": target_permit_types}},
        *document_context,
    ]

    jurisdiction = None
    building = None
    site = None
    if "zoning" in selected:
        await _emit_progress(on_progress, brief, phase="waiting_jurisdiction", completed=completed)
        jurisdiction = await _run_section(
            AnalysisSection.JURISDICTION,
            brief,
            review_document_context,
            authoritative_context=authoritative_context,
        )
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
        building = await _run_section(
            AnalysisSection.BUILDING,
            brief,
            review_document_context,
            authoritative_context=authoritative_context,
        )
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
        site = await _run_section(
            AnalysisSection.SITE,
            brief,
            review_document_context,
            authoritative_context=authoritative_context,
        )
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

    if jurisdiction and building and site:
        summary = merge_reports(brief, jurisdiction, building, site)
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
        package = await _run_section(
            AnalysisSection.PACKAGING,
            brief,
            review_document_context,
            jurisdiction=jurisdiction,
            building=building,
            site=site,
            authoritative_context=authoritative_context,
            target_permit_types=target_permit_types,
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
        from shared.analysis.custom_rules import evaluate_custom_rules

        custom_checks = await evaluate_custom_rules(
            brief,
            custom_rules,
            document_context=document_context,
            target_permit_types=target_permit_types,
            authoritative_context=authoritative_context,
        )

    if brief.jurisdiction in SUPPORTED_PERMIT_JURISDICTIONS:
        from shared.schemas.case import HumanAction, ReadinessScore

        failures = sum(check.status == CheckStatus.FAIL for check in custom_checks)
        warnings = sum(check.status == CheckStatus.WARN for check in custom_checks)
        summary.readiness_score = (
            ReadinessScore.READY
            if custom_checks and not failures and not warnings
            else ReadinessScore.NEEDS_CHANGES
        )
        summary.conflicts = []
        summary.human_actions_required = [
            HumanAction(
                action="resolve_permit_review_findings",
                description=(
                    f"Resolve {failures} failed and {warnings} unverified permit review checks."
                    if failures or warnings
                    else "Review and approve the evidence-backed permit analysis before filing."
                ),
                priority="high" if failures else "normal",
            )
        ]
        summary.executive_summary = (
            f"EstatePermit evaluated {len(custom_checks)} permit-specific checks: "
            f"{failures} failed, {warnings} require evidence or review, and "
            f"{len(custom_checks) - failures - warnings} passed."
        )

    def evt(source: str, event_type: str, detail: str):
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "event_type": event_type,
            "detail": detail,
            "payload": {},
        }

    activity = [evt("analysis", "started", "Direct analysis started")]
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
            "label": "Permit review checks",
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
        "analysis_provider": "zenmux",
        "selected_modules": list(selected),
        "module_requirements": module_requirements,
        "target_permit_types": target_permit_types,
        "rule_groups": rule_groups,
    }
