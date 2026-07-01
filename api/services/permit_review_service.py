from __future__ import annotations

from typing import Any

from shared.schemas.permit_review import CandidatePermit, PermitDocumentRequirement, ProjectFact, ProjectSummary
from shared.schemas.project_brief import ProjectBrief, ProjectType
from shared.tools.knowledge import load_json


def build_project_summary(brief: ProjectBrief) -> ProjectSummary:
    facts = [
        ProjectFact(key="address", label="Address", value=brief.address, source="project_brief"),
        ProjectFact(key="jurisdiction", label="Jurisdiction", value=brief.jurisdiction, source="project_brief"),
        ProjectFact(key="project_type", label="Project type", value=brief.project_type.value, source="project_brief"),
    ]

    if brief.gross_sqft:
        facts.append(
            ProjectFact(
                key="gross_sqft",
                label="Gross square feet",
                value=str(brief.gross_sqft),
                source="project_brief",
            )
        )
    if brief.scope_of_work:
        facts.append(
            ProjectFact(key="scope_of_work", label="Scope of work", value=brief.scope_of_work, source="project_brief")
        )
    if brief.trade_scopes:
        facts.append(
            ProjectFact(
                key="trade_scopes",
                label="Trades involved",
                value=", ".join(brief.trade_scopes),
                source="project_brief",
            )
        )

    narrative = (
        f"{brief.project_name} is a {brief.project_type.value.replace('_', ' ')} project in {brief.jurisdiction}."
    )
    if brief.scope_of_work:
        narrative = f"{narrative} Scope: {brief.scope_of_work}."

    city = brief.jurisdiction.split("_")[0].title()
    return ProjectSummary(city=city, project_type=brief.project_type.value, narrative=narrative, facts=facts)


def detect_candidate_permits(brief: ProjectBrief) -> list[CandidatePermit]:
    catalog = load_json("permit_catalog.json", brief.jurisdiction)
    permit_types = catalog.get("permit_types") or catalog.get("permits") or []

    detected: list[CandidatePermit] = []
    for permit in permit_types:
        reason = _permit_reason(brief, permit)
        if not reason:
            continue
        detected.append(
            CandidatePermit(
                permit_key=permit["id"],
                label=permit.get("permit_name", permit["id"]),
                agency=permit.get("agency", "Unknown agency"),
                reason=reason,
                confidence=1.0 if permit_applies_directly(brief, permit) else 0.75,
            )
        )
    return detected


def get_required_documents(jurisdiction: str, permit_key: str) -> list[PermitDocumentRequirement]:
    requirements = load_json("document_requirements.json", jurisdiction)
    docs = requirements.get(permit_key, [])
    return [PermitDocumentRequirement.model_validate(item) for item in docs]


def permit_applies_directly(brief: ProjectBrief, permit: dict[str, Any]) -> bool:
    applies_when = set(permit.get("applies_when", []))
    if brief.project_type == ProjectType.COMMERCIAL_TENANT_IMPROVEMENT and "commercial_tenant_improvement" in applies_when:
        return True
    if brief.change_of_use and "change_of_use" in applies_when:
        return True
    if "mechanical" in brief.trade_scopes or "hvac" in brief.trade_scopes:
        if "hvac_work" in applies_when or "commercial_tenant_improvement" in applies_when:
            return True
    if "plumbing" in brief.trade_scopes and ("plumbing_work" in applies_when or "fixture_relocation" in applies_when):
        return True
    if "electrical" in brief.trade_scopes and ("electrical_work" in applies_when or "low_voltage_work" in applies_when):
        return True
    if brief.fire_alarm_work and "fire_alarm_work" in applies_when:
        return True
    if brief.sprinkler_work and "sprinkler_work" in applies_when:
        return True
    if brief.right_of_way_impacts and "right_of_way_impacts" in applies_when:
        return True
    if "kitchen_hood" in brief.trade_scopes and "kitchen_hood_work" in applies_when:
        return True
    return False


def _permit_reason(brief: ProjectBrief, permit: dict[str, Any]) -> str | None:
    permit_name = permit.get("permit_name", permit.get("id", "permit"))
    if permit_applies_directly(brief, permit):
        return f"{permit_name} applies based on the project scope and declared trade work."

    applies_when = set(permit.get("applies_when", []))
    if brief.project_type == ProjectType.COMMERCIAL_TENANT_IMPROVEMENT and "interior_alteration" in applies_when:
        return f"{permit_name} is a standard review track for Seattle commercial tenant improvement work."
    return None

