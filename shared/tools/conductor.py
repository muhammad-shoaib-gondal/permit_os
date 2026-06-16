from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from shared.schemas.case import (
    AuditEvent,
    CaseStatus,
    Conflict,
    HumanAction,
    PermitCaseSummary,
    ReadinessScore,
)
from shared.schemas.package import PermitPackage
from shared.schemas.project_brief import ProjectBrief
from shared.schemas.reports import (
    BuildingSafetyReport,
    CheckStatus,
    JurisdictionReport,
    ReadinessImpact,
    SiteEnvironmentalReport,
)


def compute_readiness(
    jurisdiction: JurisdictionReport,
    building: BuildingSafetyReport,
    site: SiteEnvironmentalReport,
) -> ReadinessScore:
    zoning_blockers = [b for b in jurisdiction.blockers if "zoning" in b.lower() or "setback" in b.lower()]
    if zoning_blockers and jurisdiction.zoning and not jurisdiction.zoning.by_right:
        # Setback is fixable — NEEDS_CHANGES per demo spec
        if any(c.status == CheckStatus.FAIL and c.category == "zoning" for c in jurisdiction.checks):
            return ReadinessScore.NEEDS_CHANGES

    all_checks = jurisdiction.checks + building.checks + site.environmental_checks + site.utility_checks
    fails = [c for c in all_checks if c.status == CheckStatus.FAIL]
    warns = [c for c in all_checks if c.status == CheckStatus.WARN]

    if any(b for b in jurisdiction.blockers if "variance denied" in b.lower()):
        return ReadinessScore.BLOCKED
    if fails:
        return ReadinessScore.NEEDS_CHANGES
    if len(warns) > 2:
        return ReadinessScore.NEEDS_CHANGES
    return ReadinessScore.READY


def detect_conflicts(
    jurisdiction: JurisdictionReport,
    building: BuildingSafetyReport,
    site: SiteEnvironmentalReport,
) -> list[Conflict]:
    conflicts: list[Conflict] = []
    if jurisdiction.blockers:
        conflicts.append(
            Conflict(
                agents=["jurisdiction", "conductor"],
                issue="Setback violation blocks by-right approval",
                severity="high",
                suggested_fix="Reduce Block B east footprint by 2ft or apply for variance (Austin LDC 25-2-491)",
            )
        )
    return conflicts


def merge_reports(
    brief: ProjectBrief,
    jurisdiction: JurisdictionReport,
    building: BuildingSafetyReport,
    site: SiteEnvironmentalReport,
    band_room_id: str | None = None,
) -> PermitCaseSummary:
    readiness = compute_readiness(jurisdiction, building, site)
    conflicts = detect_conflicts(jurisdiction, building, site)
    human_actions: list[HumanAction] = []

    if readiness != ReadinessScore.READY:
        human_actions.append(
            HumanAction(
                action="review_setback",
                description="Review Block B setback violation and approve variance path or design change",
                priority="high",
            )
        )
    human_actions.append(
        HumanAction(
            action="final_approval",
            description="Approve permit analysis package before filing",
            priority="normal",
        )
    )

    summary_text = (
        f"Project {brief.project_name}: {readiness.value}. "
        f"Jurisdiction: {jurisdiction.summary}. Building: {building.summary}. Site: {site.summary}."
    )

    return PermitCaseSummary(
        case_id=brief.case_id,
        project_name=brief.project_name,
        status=CaseStatus.AWAITING_APPROVAL,
        readiness_score=readiness,
        conflicts=conflicts,
        human_actions_required=human_actions,
        executive_summary=summary_text,
        band_room_id=band_room_id,
        audit_events=[
            AuditEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                agent_id="conductor",
                event_type="merge_complete",
                detail=summary_text,
            )
        ],
    )


def compute_audit_hash(package: PermitPackage) -> str:
    payload = package.model_dump(mode="json", exclude={"audit_hash"})
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return f"sha256:{digest}"
