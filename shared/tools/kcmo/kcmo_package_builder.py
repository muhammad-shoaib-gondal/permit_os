"""Assemble KCMO analysis package from deterministic tools."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from shared.schemas.case import CaseStatus, HumanAction, PermitCaseSummary, ReadinessScore
from shared.schemas.kcmo_intake import FindingStatus, KcmoFinding, KcmoIntake
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
from shared.tools.conductor import compute_audit_hash
from shared.tools.kcmo.kcmo_building_tools import check_kcmo_building
from shared.tools.kcmo.kcmo_fee_tools import estimate_kcmo_fees
from shared.tools.kcmo.kcmo_occupancy_tools import check_kcmo_occupancy
from shared.tools.kcmo.kcmo_permit_router import route_kcmo_permits
from shared.tools.kcmo.kcmo_site_tools import run_kcmo_site_checks
from shared.tools.kcmo.kcmo_trade_tools import check_kcmo_trade_permits
from shared.tools.kcmo.kcmo_zoning_tools import run_kcmo_zoning_checks


def _to_check(finding: KcmoFinding) -> CheckResult:
    status_map = {
        FindingStatus.PASS: CheckStatus.PASS,
        FindingStatus.FAIL: CheckStatus.FAIL,
        FindingStatus.WARN: CheckStatus.WARN,
        FindingStatus.DATA_GAP: CheckStatus.WARN,
    }
    detail = finding.explanation
    if finding.status == FindingStatus.DATA_GAP:
        detail = f"DATA_GAP: {finding.explanation}"
    if finding.next_action:
        detail = f"{detail} Next: {finding.next_action}"
    return CheckResult(
        rule=finding.finding,
        status=status_map[finding.status],
        citation=finding.citation,
        detail=detail,
        category=finding.module,
    )


def _readiness(findings: list[KcmoFinding]) -> ReadinessImpact:
    if any(f.status == FindingStatus.FAIL for f in findings):
        return ReadinessImpact.BLOCKED
    if any(f.status in (FindingStatus.WARN, FindingStatus.DATA_GAP) for f in findings):
        return ReadinessImpact.NEEDS_CHANGES
    return ReadinessImpact.READY


def build_kcmo_package(
    brief: ProjectBrief,
    intake: KcmoIntake,
    zoning_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    permits = route_kcmo_permits(intake, zoning_profile)
    zoning_findings = run_kcmo_zoning_checks(intake, zoning_profile)
    building_findings = check_kcmo_building(intake)
    trade_findings = check_kcmo_trade_permits(intake)
    site_findings = run_kcmo_site_checks(intake)
    occupancy_findings = check_kcmo_occupancy(intake)
    fees = estimate_kcmo_fees(intake)

    all_findings = zoning_findings + building_findings + trade_findings + site_findings + occupancy_findings
    data_gaps = [
        f.finding
        for f in all_findings
        if f.status == FindingStatus.DATA_GAP
    ]
    for gap_list in (f.required_user_data for f in all_findings if f.required_user_data):
        data_gaps.extend(gap_list)
    # unique preserve order
    seen: set[str] = set()
    unique_gaps: list[str] = []
    for g in data_gaps:
        if g not in seen:
            seen.add(g)
            unique_gaps.append(g)

    district = (zoning_profile or {}).get("district") or "Unknown"
    jurisdiction_report = JurisdictionReport(
        case_id=brief.case_id,
        summary=f"KCMO zoning feasibility for {district}: {len(zoning_findings)} checks.",
        readiness_impact=_readiness(zoning_findings),
        jurisdictions=[
            JurisdictionInfo(
                name="Kansas City, Missouri",
                type="city",
                codes_applicable=["Chapter 88", "Chapter 18", "Chapter 28"],
            )
        ],
        zoning=ZoningInfo(
            district=district,
            permitted_use=intake.proposed_use or "unspecified",
            by_right=False,
        ),
        checks=[_to_check(f) for f in zoning_findings],
        blockers=[f.finding for f in zoning_findings if f.status == FindingStatus.FAIL],
        data_gaps=[f.finding for f in zoning_findings if f.status == FindingStatus.DATA_GAP],
    )

    building_report = BuildingSafetyReport(
        case_id=brief.case_id,
        summary=f"KCMO building/trade/fire checks: {len(building_findings) + len(trade_findings)} findings.",
        readiness_impact=_readiness(building_findings + trade_findings + occupancy_findings),
        checks=[_to_check(f) for f in building_findings + trade_findings + occupancy_findings],
        blockers=[f.finding for f in building_findings if f.status == FindingStatus.FAIL],
        recommendations=[f.next_action for f in building_findings + occupancy_findings if f.next_action],
    )

    site_report = SiteEnvironmentalReport(
        case_id=brief.case_id,
        summary=f"KCMO site/floodplain checks: {len(site_findings)} findings.",
        readiness_impact=_readiness(site_findings),
        environmental_checks=[_to_check(f) for f in site_findings],
        utility_checks=[],
        additional_permits=[
            p["permit_name"]
            for p in permits
            if p["permit_type"] in ("floodplain_development", "right_of_way", "public_improvement_review")
        ],
        blockers=[f.finding for f in site_findings if f.status == FindingStatus.FAIL],
    )

    package = PermitPackage(
        case_id=brief.case_id if isinstance(brief.case_id, UUID) else UUID(str(brief.case_id)),
        permits_required=[
            PermitRequirement(
                permit_name=p["permit_name"],
                agency=p.get("issuing_authority") or "Kansas City, Missouri",
                form_id=p.get("permit_type") or p["permit_name"],
                fee_usd=float(p.get("estimated_fee_usd") or 0),
                timeline_days=30,
                dependencies=list(p.get("dependencies") or []),
            )
            for p in permits
            if p.get("requirement_status") != "not_required"
        ],
        documents_required=[
            DocumentRequirement(
                name="See Ready-to-File Checklist (IB100/IB110 package)",
                source_agent="kcmo_checklist",
            )
        ],
        filing_sequence=[p["permit_name"] for p in permits if p.get("requirement_status") == "required"],
        estimated_timeline_days=45,
        total_fees_estimate_usd=0,
    )
    if package.permits_required:
        package.audit_hash = compute_audit_hash(package)

    impact = _readiness(all_findings)
    readiness = {
        ReadinessImpact.READY: ReadinessScore.READY,
        ReadinessImpact.NEEDS_CHANGES: ReadinessScore.NEEDS_CHANGES,
        ReadinessImpact.BLOCKED: ReadinessScore.BLOCKED,
    }[impact]

    summary = PermitCaseSummary(
        case_id=brief.case_id,
        project_name=brief.project_name,
        status=CaseStatus.AWAITING_APPROVAL,
        readiness_score=readiness,
        executive_summary=(
            f"KCMO pre-screen for {intake.project_category.value.replace('_', ' ')} / "
            f"{intake.scope_type.value.replace('_', ' ')}: {len(permits)} likely permits, "
            f"{len(unique_gaps)} data gap(s). Confirm all requirements in CompassKC."
        ),
        human_actions_required=[
            HumanAction(action="resolve_data_gap", description=gap, priority="high")
            for gap in unique_gaps[:12]
        ],
    )

    serialized_findings = [f.model_dump(mode="json") for f in all_findings]

    return {
        "likely_permits": permits,
        "findings": serialized_findings,
        "data_gaps": unique_gaps,
        "fee_estimate": fees,
        "jurisdiction_report": jurisdiction_report.model_dump(mode="json"),
        "building_report": building_report.model_dump(mode="json"),
        "site_report": site_report.model_dump(mode="json"),
        "case_summary": summary.model_dump(mode="json"),
        "permit_package": package.model_dump(mode="json"),
        "kcmo": True,
    }
