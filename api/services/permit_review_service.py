from __future__ import annotations

from typing import Any

from shared.schemas.permit_review import CandidatePermit, PermitDocumentRequirement, ProjectFact, ProjectSummary
from shared.schemas.project_brief import ProjectBrief, ProjectType
from shared.tools.kcmo_permits import match_kcmo_applications
from shared.tools.kck_permits import match_kck_applications
from shared.tools.lenexa_permits import match_lenexa_applications
from shared.tools.overland_park_permits import match_overland_park_applications
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
    if brief.jurisdiction == "kansas_city_mo":
        for application in match_kcmo_applications(
            _brief_scope(brief),
            brief.project_type.value,
            {"fire_alarm": brief.fire_alarm_work},
        ):
            detected.append(
                CandidatePermit(
                    permit_key=f"compass_{application['application_kind']}_{application['id']}",
                    label=application["name"],
                    agency="Kansas City, Missouri",
                    reason=application["reason"],
                    confidence=1.0 if application["requirement_status"] == "required" else 0.75,
                )
            )
    elif brief.jurisdiction == "kansas_city_ks":
        for application in match_kck_applications(_brief_scope(brief), brief.project_type.value):
            detected.append(
                CandidatePermit(
                    permit_key=f"kck_{application['id']}",
                    label=application["name"],
                    agency=application["authority"],
                    reason=application["reason"],
                    confidence=1.0 if application["requirement_status"] == "required" else 0.75,
                )
            )
    elif brief.jurisdiction in {"lenexa_ks", "overland_park_ks"}:
        matcher = match_lenexa_applications if brief.jurisdiction == "lenexa_ks" else match_overland_park_applications
        prefix = "lenexa" if brief.jurisdiction == "lenexa_ks" else "overland_park"
        for application in matcher(_brief_scope(brief), brief.project_type.value):
            detected.append(CandidatePermit(
                permit_key=f"{prefix}_{application['id']}", label=application["name"],
                agency=application["authority"], reason=application["reason"],
                confidence=1.0 if application["requirement_status"] == "required" else 0.75,
            ))
    return detected


def get_required_documents(jurisdiction: str, permit_key: str) -> list[PermitDocumentRequirement]:
    requirements = load_json("document_requirements.json", jurisdiction)
    docs = requirements.get(permit_key, [])
    return [PermitDocumentRequirement.model_validate(item) for item in docs]


def permit_applies_directly(brief: ProjectBrief, permit: dict[str, Any]) -> bool:
    applies_when = set(permit.get("applies_when_any") or permit.get("applies_when") or [])
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

    applies_when = set(permit.get("applies_when_any") or permit.get("applies_when") or [])
    if brief.project_type == ProjectType.COMMERCIAL_TENANT_IMPROVEMENT and "interior_alteration" in applies_when:
        return f"{permit_name} is a standard review track for commercial tenant improvement work."
    return None


def _brief_scope(brief: ProjectBrief) -> dict[str, bool]:
    trades = {trade.casefold() for trade in brief.trade_scopes}
    scope = (brief.scope_of_work or "").casefold()
    return {
        "new_construction": "new construction" in scope,
        "addition": "addition" in scope,
        "alteration": any(word in scope for word in ("alteration", "remodel", "renovation", "tenant finish")),
        "repair": "repair" in scope,
        "demolition": "demolition" in scope or "demo" in scope,
        "structural_work": "structural" in trades or "structural" in scope,
        "electrical_work": "electrical" in trades,
        "plumbing_work": "plumbing" in trades,
        "mechanical_hvac_work": bool(trades.intersection({"mechanical", "hvac", "kitchen_hood"})),
        "fire_alarm_sprinkler_work": brief.fire_alarm_work or brief.sprinkler_work,
        "signs": "sign" in trades or "signage" in scope,
        "change_use_occupancy": brief.change_of_use,
        "grading_land_disturbance": bool(trades.intersection({"grading", "land_disturbance"})),
        "driveway_sidewalk_row": brief.right_of_way_impacts,
        "solar_battery_generator_ev": bool(trades.intersection({"solar", "battery", "generator", "ev"})),
        "water_sewer_connections": bool(trades.intersection({"water", "sewer", "utility"})),
    }
