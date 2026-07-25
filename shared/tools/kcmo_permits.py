from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from shared.tools.knowledge import load_json

PORTAL_BASE = "https://compasskc.kcmo.org/EnerGov_Prod/SelfService"

SCOPE_CATEGORY_PREFIXES: dict[str, tuple[str, ...]] = {
    "new_construction": ("Building - Commercial", "Building - Residential"),
    "addition": ("Building - Commercial", "Building - Residential"),
    "alteration": ("Building - Commercial", "Building - Residential"),
    "repair": ("Building - Commercial", "Building - Residential"),
    "demolition": ("Demolition",),
    "structural_work": ("Building - Commercial", "Building - Residential"),
    "electrical_work": ("Building - Electrical",),
    "plumbing_work": ("Building - Plumbing",),
    "mechanical_hvac_work": ("Building - Mechanical", "Building - Fire Protection"),
    "fire_alarm_sprinkler_work": ("Building - Electrical", "Building - Fire Protection"),
    "signs": ("Building - Signs",),
    "grading_land_disturbance": ("Street - Infrastructure", "Street - Excavation"),
    "driveway_sidewalk_row": ("Street -", "Streetcar Zone Access"),
    "solar_battery_generator_ev": ("Building - Electrical",),
    "water_sewer_connections": ("Building - Plumbing", "Water -"),
    "change_use_occupancy": ("Zoning", "Building - Commercial"),
}

PLAN_SCOPE_CATEGORY_PREFIXES: dict[str, tuple[str, ...]] = {
    "new_construction": (
        "Building - Administrative Reviews", "Building - Commercial Application",
        "Building - Residential Application", "City Infrastructure", "Planning - Land Use",
        "Planning - Plan Approvals", "Planning - Subdivide", "Planning - Zoning Adjustments",
    ),
    "addition": (
        "Building - Administrative Reviews", "Building - Commercial Application",
        "Building - Residential Application", "Planning - Historic Preservation",
        "Planning - Plan Approvals", "Planning - Zoning Adjustments",
    ),
    "alteration": (
        "Building - Administrative Reviews", "Building - Commercial Application",
        "Building - Residential Application", "Planning - Historic Preservation",
        "Planning - Plan Approvals", "Planning - Zoning Adjustments",
    ),
    "repair": ("Building - Administrative Reviews", "Planning - Historic Preservation"),
    "demolition": ("Building - Administrative Reviews", "Planning - Historic Preservation"),
    "structural_work": (
        "Building - Administrative Reviews", "Building - Commercial Application",
        "Building - Residential Application",
    ),
    "electrical_work": ("Building - Administrative Reviews", "Building - Commercial Application"),
    "plumbing_work": ("Building - Administrative Reviews", "Building - Commercial Application"),
    "mechanical_hvac_work": ("Building - Administrative Reviews", "Building - Commercial Application"),
    "fire_alarm_sprinkler_work": ("Building - Commercial Application",),
    "signs": ("Planning - Sign Applications", "Planning - Zoning Adjustments"),
    "change_use_occupancy": (
        "Building - Administrative Reviews", "Building - Commercial Application",
        "Planning - File an Appeal", "Planning - Historic Preservation", "Planning - Land Use",
        "Planning - Other", "Planning - Plan Approvals", "Planning - Zoning Adjustments",
        "PMAB - Property Maintenance Appeals Board",
    ),
    "grading_land_disturbance": (
        "Building - Administrative Reviews", "Building - Commercial Application",
        "City Infrastructure", "Planning - Easement Processing", "Planning - Plan Approvals",
        "Planning - Subdivide", "Planning - Zoning Adjustments",
    ),
    "driveway_sidewalk_row": (
        "City Infrastructure", "Planning - Easement Processing", "Planning - Street Related",
        "Planning - Subdivide", "Planning - Zoning Adjustments",
    ),
    "solar_battery_generator_ev": ("Building - Residential Application", "Building - Commercial Application"),
    "water_sewer_connections": (
        "City Infrastructure", "Planning - Easement Processing", "Planning - Plan Approvals",
    ),
}


def compass_url(application_kind: str, application_id: int) -> str:
    route = "permit" if application_kind == "permit" else "plan"
    return f"{PORTAL_BASE}#/{route}/apply/{application_id}/0/0"


def load_compass_catalog() -> dict[str, Any]:
    return load_json("compass_catalog.json", "kansas_city_mo")  # type: ignore[return-value]


def load_permit_rules() -> dict[str, Any]:
    return load_json("permit_rules.json", "kansas_city_mo")  # type: ignore[return-value]


def all_applications(application_kind: str = "permit") -> list[dict[str, Any]]:
    catalog = load_compass_catalog()
    key = "permit_applications" if application_kind == "permit" else "plan_applications"
    return [_decorate(item, application_kind) for item in catalog[key]]


def applications_for_category(category: str, *, application_kind: str = "permit") -> list[dict[str, Any]]:
    target = _normalize(category)
    return [item for item in all_applications(application_kind) if _category_matches(item["category"], target)]


def match_kcmo_applications(
    scope: dict[str, bool] | None,
    project_type: str,
    facts: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return every selected-category route with deterministic applicability status.

    Known building-type incompatibilities are retained as not_required audit records. Compatible
    conditional routes remain visible. Vector search and LLMs never decide applicability.
    """
    facts = facts or {}
    active_scope = {key for key, enabled in (scope or {}).items() if enabled}
    prefixes = _ordered_unique(
        prefix for scope_key in active_scope for prefix in SCOPE_CATEGORY_PREFIXES.get(scope_key, ())
    )
    permit_candidates = [
        item
        for item in all_applications("permit")
        if any(item["category"].startswith(prefix) for prefix in prefixes)
    ]
    plan_prefixes = _ordered_unique(
        prefix
        for scope_key in active_scope
        for prefix in PLAN_SCOPE_CATEGORY_PREFIXES.get(scope_key, ())
    )
    plan_candidates = [
        item
        for item in all_applications("plan")
        if any(item["category"].startswith(prefix) for prefix in plan_prefixes)
    ]

    results: list[dict[str, Any]] = []
    for item in permit_candidates:
        status, reasons = _classify(item, active_scope, project_type, facts)
        family = rule_family_for_category(item["category"])
        results.append(
            {
                **item,
                "requirement_status": status,
                "reason": "; ".join(reasons),
                "rule_family_id": family.get("id") if family else None,
                "sources": list(family.get("sources", [])) if family else [],
                "questions": questions_for_application(item, facts),
            }
        )

    explicit_dependencies = {
        item["id"]: item for item in _plan_dependencies(active_scope, project_type, facts)
    }
    for item in plan_candidates:
        if item["id"] in explicit_dependencies:
            results.append(explicit_dependencies.pop(item["id"]))
            continue
        status, reasons = _classify_plan(item, active_scope, project_type, facts)
        family = rule_family_for_category(item["category"])
        results.append({
            **item,
            "requirement_status": status,
            "reason": "; ".join(reasons),
            "rule_family_id": family.get("id") if family else None,
            "sources": list(family.get("sources", [])) if family else [],
            "questions": questions_for_application(item, facts),
        })
    results.extend(explicit_dependencies.values())
    return sorted(results, key=lambda item: (item["application_kind"] != "permit", item["category"], item["id"]))


def rule_family_for_category(category: str) -> dict[str, Any] | None:
    matches: list[tuple[int, dict[str, Any]]] = []
    rules = load_permit_rules()
    for family in [*rules.get("category_rules", []), *rules.get("plan_category_rules", [])]:
        for prefix in family.get("category_prefixes", []):
            if category.startswith(prefix):
                matches.append((len(prefix), family))
    return max(matches, key=lambda item: item[0])[1] if matches else None


def _classify_plan(
    item: dict[str, Any], active_scope: set[str], project_type: str, facts: dict[str, Any]
) -> tuple[str, list[str]]:
    reasons = ["included from the complete selected CompassKC plan category"]
    answered = _answered_applicability(item, facts)
    name = _normalize(item["name"])
    residential = _is_residential(project_type)
    commercial = not residential
    if _known_incompatible_variant(name, commercial, residential, "townhouse" in _normalize(project_type)):
        return "not_required", reasons + ["plan building type conflicts with the selected project type"]
    if "demolition" in active_scope and "demolition review" in name:
        return "required", reasons + ["demolition scope requires historic-resource applicability review"]
    if answered is not None:
        return (
            ("required", reasons + ["the project-specific applicability question was answered yes"])
            if answered
            else ("not_required", reasons + ["the project-specific applicability question was answered no"])
        )
    if "signs" in active_scope and "sign" in name:
        return "needs_confirmation", reasons + ["sign design and requested deviation determine this plan route"]
    if "change_use_occupancy" in active_scope and any(token in name for token in ("rezoning", "special use", "legal nonconformance", "occupancy")):
        return "needs_confirmation", reasons + ["proposed use and existing approvals determine this route"]
    return "needs_confirmation", reasons + ["project facts and agency review must confirm or exclude this exact plan route"]


def _classify(
    item: dict[str, Any], active_scope: set[str], project_type: str, facts: dict[str, Any]
) -> tuple[str, list[str]]:
    category = item["category"]
    application_id = item["id"]
    reasons = ["included from the complete selected CompassKC category"]
    answered = _answered_applicability(item, facts)

    if category == "Building - Electrical":
        status, electrical_reasons = _classify_electrical(
            application_id, active_scope, project_type, facts, reasons
        )
        if status != "needs_confirmation" or answered is None:
            return status, electrical_reasons
        return (
            ("required", electrical_reasons + ["the project-specific applicability question was answered yes"])
            if answered
            else ("not_required", electrical_reasons + ["the project-specific applicability question was answered no"])
        )

    name = _normalize(item["name"])
    residential = _is_residential(project_type)
    townhouse = "townhouse" in _normalize(project_type)
    commercial = not residential

    if _known_incompatible_variant(name, commercial, residential, townhouse):
        return "not_required", reasons + ["application building type conflicts with the selected project type"]

    if answered is True:
        return "required", reasons + ["the project-specific applicability question was answered yes"]

    if "demolition" in active_scope and category == "Demolition":
        if (commercial and "commercial" in name) or (residential and "residential" in name):
            return (
                "not_required" if answered is False else "needs_confirmation",
                reasons + ["the project-specific applicability question was answered no" if answered is False else "building type matches; demolition subtype must be confirmed"],
            )
    if category == "Building - Plumbing" and "plumbing_work" in active_scope:
        if _building_variant_matches(name, commercial, residential, townhouse):
            if "general" in name:
                return "required", reasons + ["general plumbing route and building type match"]
            return (
                "not_required" if answered is False else "needs_confirmation",
                reasons + ["the project-specific applicability question was answered no" if answered is False else "building type matches; specialized plumbing scope must be confirmed"],
            )
    if category == "Building - Mechanical" and "mechanical_hvac_work" in active_scope:
        if _building_variant_matches(name, commercial, residential, townhouse):
            if "general" in name:
                return "required", reasons + ["general mechanical route and building type match"]
            return (
                "not_required" if answered is False else "needs_confirmation",
                reasons + ["the project-specific applicability question was answered no" if answered is False else "building type matches; specialized mechanical scope must be confirmed"],
            )
    if answered is False:
        return "not_required", reasons + ["the project-specific applicability question was answered no"]
    if category == "Building - Signs" and "signs" in active_scope:
        return "needs_confirmation", reasons + ["sign form and duration are not yet specified"]
    if category.startswith("Water -") and "water_sewer_connections" in active_scope:
        return "needs_confirmation", reasons + ["service-line operation is not yet specified"]
    if category.startswith("Street -") or category == "Streetcar Zone Access":
        return "needs_confirmation", reasons + ["right-of-way activity and location must identify the exact route"]
    if category == "Zoning" and "change_use_occupancy" in active_scope:
        return "needs_confirmation", reasons + ["proposed use and requested zoning record must be confirmed"]
    if category == "Building - Fire Protection" and "fire_alarm_sprinkler_work" in active_scope:
        if "construction or modification" in name and "sprinkler" in name:
            return "required", reasons + ["fire-sprinkler scope matches the standard system route"]
        return "needs_confirmation", reasons + ["system type and building type must identify the exact route"]
    if category == "Building - Commercial" and commercial:
        return "needs_confirmation", reasons + ["commercial route matches; construction subtype must be confirmed"]
    if category == "Building - Residential" and residential:
        return "needs_confirmation", reasons + ["residential route matches; construction subtype must be confirmed"]
    if category.startswith("Building -"):
        return "needs_confirmation", reasons + ["construction subtype and plan-review need must be confirmed"]
    return "needs_confirmation", reasons


def _classify_electrical(
    application_id: int,
    active_scope: set[str],
    project_type: str,
    facts: dict[str, Any],
    reasons: list[str],
) -> tuple[str, list[str]]:
    residential = _is_residential(project_type)
    townhouse = "townhouse" in _normalize(project_type)
    reconnect = bool(facts.get("electrical_reconnect"))
    limited = bool(facts.get("limited_service"))
    fire_alarm = bool(facts.get("fire_alarm")) or "fire_alarm_sprinkler_work" in active_scope
    security_alarm = bool(facts.get("security_alarm"))

    exact_matches: dict[int, bool] = {
        576: not residential and "electrical_work" in active_scope and not reconnect,
        767: residential and townhouse and not reconnect and not limited,
        583: residential and not townhouse and not reconnect and not limited,
        434: residential and limited,
        430: not residential and reconnect,
        431: residential and reconnect,
        772: not residential and fire_alarm,
        432: residential and security_alarm,
    }
    if exact_matches.get(application_id):
        return "required", reasons + ["project facts match this exact electrical route"]
    commercial_ids = {576, 430, 772}
    residential_ids = {767, 583, 434, 431, 432}
    if (residential and application_id in commercial_ids) or (not residential and application_id in residential_ids):
        return "not_required", reasons + ["electrical application building type conflicts with the selected project type"]
    if application_id in {576, 430, 431, 434, 583, 767, 432} and "electrical_work" not in active_scope:
        return "not_required", reasons + ["general electrical scope was not selected"]
    if application_id == 772 and not fire_alarm:
        return "not_required", reasons + ["fire-alarm scope was not selected"]
    return "needs_confirmation", reasons + ["kept visible until electrical subtype facts exclude it"]


def _plan_dependencies(
    active_scope: set[str], project_type: str, facts: dict[str, Any]
) -> list[dict[str, Any]]:
    plans = {item["id"]: item for item in all_applications("plan")}
    selected: list[tuple[int, str, str]] = []
    residential = _is_residential(project_type)
    if "solar_battery_generator_ev" in active_scope and residential and facts.get("solar", True):
        selected.append((923, "required", "residential solar requires the Residential Solar Plan application"))
    if "electrical_work" in active_scope and not residential and facts.get("formal_trade_plans_required"):
        selected.append((653, "required", "commercial electrical plans require the trade-only plan route"))
    if facts.get("fire_alarm") and not residential and facts.get("formal_trade_plans_required"):
        selected.append((653, "required", "commercial fire-alarm plans require the trade-only plan route"))
    if "fire_alarm_sprinkler_work" in active_scope and facts.get("sprinkler_plan_required", True):
        selected.append((652, "required", "fire-sprinkler construction/modification requires its plan review"))
    output: list[dict[str, Any]] = []
    seen: set[int] = set()
    for plan_id, status, reason in selected:
        if plan_id in seen:
            continue
        seen.add(plan_id)
        item = plans[plan_id]
        output.append({
            **item,
            "requirement_status": status,
            "reason": reason,
            "rule_family_id": "electrical" if plan_id in {923, 653} else "fire_protection",
            "sources": ["compass_application_assistant", "ib160"] if plan_id in {923, 653} else ["compass_application_assistant", "ib116"],
            "questions": questions_for_application(item, facts),
        })
    return output


def _decorate(item: dict[str, Any], application_kind: str) -> dict[str, Any]:
    return {
        **item,
        "application_kind": application_kind,
        "portal_url": compass_url(application_kind, int(item["id"])),
    }


def application_answer_key(item: dict[str, Any]) -> str:
    return f"kcmo_{item.get('application_kind', 'permit')}_{int(item['id'])}_applies"


def questions_for_application(
    item: dict[str, Any], facts: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    key = application_answer_key(item)
    return [{
        "key": key,
        "type": "boolean",
        "label": f"Does this project include work or approvals requiring {item['name']}?",
        "help": (
            f"This is the exact CompassKC {item.get('application_kind', 'permit')} workflow "
            f"in {item['category']}. Leave unanswered when uncertain so EstatePermit keeps it visible."
        ),
        "answer": (facts or {}).get(key),
    }]


def _answered_applicability(item: dict[str, Any], facts: dict[str, Any]) -> bool | None:
    value = facts.get(application_answer_key(item))
    return value if isinstance(value, bool) else None


def _category_matches(actual: str, normalized_target: str) -> bool:
    actual_normalized = _normalize(actual)
    aliases = {
        "electrical": "building electrical",
        "plumbing": "building plumbing",
        "mechanical": "building mechanical",
        "fire protection": "building fire protection",
        "residential": "building residential",
        "commercial": "building commercial",
        "signs": "building signs",
        "water": "water",
        "street": "street",
        "right of way": "street",
    }
    target = aliases.get(normalized_target, normalized_target)
    return actual_normalized == target or actual_normalized.startswith(target)


def _is_residential(project_type: str) -> bool:
    value = _normalize(project_type)
    return any(token in value for token in ("single family", "duplex", "townhouse", "residential")) and "multifamily" not in value


def _building_variant_matches(name: str, commercial: bool, residential: bool, townhouse: bool) -> bool:
    if townhouse and "townhouse" in name:
        return True
    if residential and not townhouse and "residential" in name:
        return True
    if commercial and "commercial" in name:
        return True
    return False


def _known_incompatible_variant(
    name: str, commercial: bool, residential: bool, townhouse: bool
) -> bool:
    residential_markers = (
        "residential",
        "single family",
        "duplex",
        "townhouse",
        "residence",
    )
    if commercial and any(marker in name for marker in residential_markers):
        return True
    if residential and "commercial" in name:
        return True
    if residential and not townhouse and "townhouse" in name:
        return True
    return False


def _normalize(value: Any) -> str:
    return " ".join(
        str(value).casefold().replace("_", " ").replace("-", " ").replace("/", " ").split()
    )


def _ordered_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))
