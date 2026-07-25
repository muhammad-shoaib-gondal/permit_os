from __future__ import annotations

import re
from typing import Any

from shared.tools.knowledge import load_json
from shared.tools.kcmo_review_rules import review_questions_for_permit


def load_approval_catalog() -> dict[str, Any]:
    return load_json("approval_catalog.json", "kansas_city_mo")  # type: ignore[return-value]


def _condition_value(condition: str | dict[str, Any], facts: dict[str, Any]) -> tuple[bool | None, str]:
    if isinstance(condition, str):
        return (bool(facts[condition]), condition) if condition in facts else (None, condition)

    key = str(condition["fact"])
    if key not in facts or facts[key] in (None, ""):
        return None, key
    actual = facts[key]
    op = condition.get("op", "equals")
    expected = condition.get("value", condition.get("equals", True))
    try:
        if op == "gte":
            return float(actual) >= float(expected), key
        if op == "gt":
            return float(actual) > float(expected), key
        if op == "lt":
            return float(actual) < float(expected), key
        if op == "lte":
            return float(actual) <= float(expected), key
    except (TypeError, ValueError):
        return None, key
    return actual == expected, key


def _evaluate_clauses(
    clauses: list[list[str | dict[str, Any]]], facts: dict[str, Any]
) -> tuple[bool, list[str], list[str]]:
    matched_facts: list[str] = []
    missing_facts: list[str] = []
    for clause in clauses:
        clause_matches = True
        clause_known = True
        clause_facts: list[str] = []
        for condition in clause:
            matched, key = _condition_value(condition, facts)
            if matched is None:
                clause_known = False
                missing_facts.append(key)
            elif not matched:
                clause_matches = False
            else:
                clause_facts.append(key)
        if clause_known and clause_matches:
            matched_facts.extend(clause_facts)
            return True, list(dict.fromkeys(matched_facts)), list(dict.fromkeys(missing_facts))
    return False, [], list(dict.fromkeys(missing_facts))


def _streetcar_corridor(address: str, profile: dict[str, Any]) -> bool | None:
    explicit = (profile.get("permitContext") or {}).get("nearStreetcar")
    if isinstance(explicit, bool):
        return explicit

    normalized = " ".join(address.casefold().replace(",", " ").split())
    latitude = profile.get("latitude")
    longitude = profile.get("longitude")
    on_main = bool(re.search(r"\bmain\s+(st|street)\b", normalized))
    try:
        in_route_bounds = 38.95 <= float(latitude) <= 39.12 and -94.60 <= float(longitude) <= -94.57
    except (TypeError, ValueError):
        in_route_bounds = False
    if on_main and in_route_bounds:
        return True
    return None


def project_approval_facts(project: Any, scope: dict[str, bool]) -> dict[str, Any]:
    profile = dict(project.zoning_profile or {})
    context = dict(profile.get("permitContext") or {})
    answers = dict(project.permit_answers or {})
    project_type = str(project.project_type or "")
    area = str(project.area or "").upper()

    facts: dict[str, Any] = {key: bool(value) for key, value in scope.items()}
    facts.update(
        {
            "jurisdiction_kcmo": project.jurisdiction == "kansas_city_mo",
            "commercial": project_type in {
                "commercial",
                "commercial_tenant_improvement",
                "new_commercial_construction",
                "mixed_use",
                "industrial",
            },
            "commercial_tenant_improvement": project_type == "commercial_tenant_improvement",
            "ur_zone": bool(re.search(r"(?:^|[/\s])UR(?:$|[/\s-])", area)),
        }
    )

    for key in ("historicLocal", "historicNational", "parcelCount", "verifiedLotCount", "developmentCaseCount"):
        if key in context:
            facts[
                {
                    "historicLocal": "historic_local",
                    "historicNational": "historic_national",
                    "parcelCount": "parcel_count",
                    "verifiedLotCount": "verified_lot_count",
                    "developmentCaseCount": "development_case_count",
                }[key]
            ] = context[key]

    near_streetcar = _streetcar_corridor(project.address, profile)
    if near_streetcar is not None:
        facts["near_streetcar"] = near_streetcar

    facts.update(answers)

    confirmation_overrides = {
        "electrical_work_confirmed": "electrical_work",
        "plumbing_work_confirmed": "plumbing_work",
        "mechanical_work_confirmed": "mechanical_hvac_work",
    }
    for answer_key, fact_key in confirmation_overrides.items():
        if answer_key in answers:
            facts[fact_key] = bool(answers[answer_key])

    if "fire_sprinkler" not in answers and scope.get("fire_alarm_sprinkler_work"):
        facts["fire_sprinkler"] = True
    if "fire_alarm" not in answers and scope.get("fire_alarm_sprinkler_work"):
        facts["fire_alarm"] = True
    if "exterior_work" not in answers and (scope.get("new_construction") or scope.get("addition")):
        facts["exterior_work"] = True
    return facts


def _question_payload(entry: dict[str, Any], answers: dict[str, Any]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for question in [
        *entry.get("questions", []),
        *review_questions_for_permit(entry["id"]),
    ]:
        if question["key"] in seen:
            continue
        seen.add(question["key"])
        questions.append({**question, "answer": answers.get(question["key"])})
    return questions


def _rule_family_id(permit_id: str) -> str:
    families = {
        "zoning": {
            "zoning_verification", "certificate_appropriateness", "ur_development_plan",
            "platting_lot_consolidation",
        },
        "commercial_building": {
            "commercial_building", "foundation_early_start", "shoring_excavation_support",
            "retaining_wall", "elevator_state", "boiler_pressure_vessel_state",
        },
        "electrical": {"electrical", "electrical_service"},
        "mechanical": {"mechanical"},
        "plumbing": {"plumbing", "gas_piping", "backflow_prevention"},
        "fire_protection": {
            "fire_sprinkler", "fire_alarm", "standpipe", "fire_pump", "errc_bda_das",
            "smoke_control", "kitchen_hood_suppression", "hazardous_materials_operational",
        },
        "demolition": {"demolition", "asbestos_neshap"},
        "street_and_row": {
            "row_excavation", "sidewalk_curb_driveway", "traffic_lane_sidewalk_closure",
            "streetcar_track_access", "encroachment_vault", "hauling_oversize",
            "crane_erection",
        },
        "major_infrastructure": {
            "land_disturbance", "modnr_construction_stormwater", "stormwater_management",
            "dust_control",
        },
        "water_service": {
            "domestic_water_service", "fire_water_service", "sanitary_sewer_connection",
            "storm_sewer_connection", "water_main_extension", "industrial_pretreatment",
        },
        "certificate_of_occupancy": {
            "temporary_certificate_occupancy", "certificate_of_occupancy",
        },
    }
    return next((family for family, permits in families.items() if permit_id in permits), permit_id)


def build_kcmo_approval_recommendations(project: Any, scope: dict[str, bool]) -> list[dict[str, Any]]:
    catalog = load_approval_catalog()
    registry = load_json("source_registry.json", "kansas_city_mo")
    source_map = {item["id"]: item for item in registry.get("sources", [])}
    facts = project_approval_facts(project, scope)
    answers = dict(project.permit_answers or {})
    recommendations: list[dict[str, Any]] = []

    for entry in catalog["approvals"]:
        required, confirmed, required_missing = _evaluate_clauses(entry.get("required_when", []), facts)
        excluded, excluded_by, excluded_missing = _evaluate_clauses(
            entry.get("not_required_when", []), facts
        )
        questions = _question_payload(entry, answers)
        unanswered = [q["key"] for q in questions if q.get("answer") in (None, "")]

        if required:
            status = "required"
            reason = "Required because the project has confirmed facts: " + ", ".join(
                key.replace("_", " ") for key in confirmed
            ) + "."
            next_action = "Prepare the listed documents and confirm the filing route."
        elif excluded:
            status = "not_required"
            reason = "Not required based on confirmed project facts: " + ", ".join(
                key.replace("_", " ") for key in excluded_by
            ) + "."
            next_action = "No filing action unless the project facts change."
        else:
            status = "needs_confirmation"
            labels = [q["label"] for q in questions if q["key"] in unanswered]
            reason = (
                "More project information is required before this approval can be classified."
                if not labels
                else "Needs information: " + " ".join(labels)
            )
            next_action = "Answer the permit-specific questions shown on this card."

        sources = [source_map[source_id] for source_id in entry.get("source_ids", []) if source_id in source_map]
        source_url = sources[0]["url"] if sources else None
        missing = list(dict.fromkeys(unanswered + required_missing + excluded_missing))
        evidence = {
            "catalogRule": {
                "permitId": entry["id"],
                "permitName": entry["permit_name"],
                "ruleFamilyId": _rule_family_id(entry["id"]),
                "sequence": entry["sequence"],
                "phase": entry["phase"],
                "sourceIds": entry.get("source_ids", []),
                "compassApplicationIds": entry.get("compass_application_ids", []),
                "compassPlanIds": entry.get("compass_plan_ids", []),
            },
            "projectFacts": {
                "jurisdiction": project.jurisdiction,
                "projectType": project.project_type,
                "selectedScope": [key for key, value in scope.items() if value],
                "answers": answers,
                "automaticFacts": {
                    key: value
                    for key, value in facts.items()
                    if key not in answers and key not in scope
                },
            },
            "matchResult": {
                "classification": status,
                "policy": "authoritative catalog with explicit project facts",
                "usesVectorOrLlm": False,
                "confirmedFacts": confirmed,
                "excludedBy": excluded_by,
                "missingFacts": missing,
            },
            "questions": questions,
        }

        recommendations.append(
            {
                "permit_type": entry["id"],
                "permit_name": entry["permit_name"],
                "issuing_authority": entry["authority"],
                "jurisdiction": project.jurisdiction,
                "requirement_status": status,
                "lifecycle_status": "gathering_documents" if status == "required" else "not_started",
                "origin": "system",
                "reason": reason,
                "recommendation_evidence": evidence,
                "source": " | ".join(source["title"] for source in sources) or None,
                "portal_url": source_url,
                "coverage_status": f"complete_45_catalog_{catalog['version']}",
                "dependencies": [],
                "required_documents": entry.get("required_documents", []),
                "estimated_fee_usd": None,
                "current_blocker": reason if status == "needs_confirmation" else None,
                "next_action": next_action,
            }
        )
    return recommendations
