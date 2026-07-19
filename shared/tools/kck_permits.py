from __future__ import annotations

from typing import Any

from shared.tools.knowledge import load_json


DIRECT_SCOPE_APPLICATIONS = {
    "electrical_work": {"electrical"},
    "mechanical_hvac_work": {"mechanical"},
    "plumbing_work": {"plumbing"},
    "demolition": {"demolition"},
    "fire_alarm_sprinkler_work": {"fire_sprinkler", "fire_alarm"},
    "signs": {"sign_incidental", "sign_flag", "sign_attached", "sign_detached", "billboard_under_300", "billboard_300_or_more"},
    "grading_land_disturbance": {"land_disturbance"},
    "driveway_sidewalk_row": {"right_of_way"},
}


def load_kck_application_catalog() -> dict[str, Any]:
    return load_json("application_catalog.json", "kansas_city_ks")  # type: ignore[return-value]


def load_kck_permit_rules() -> dict[str, Any]:
    return load_json("permit_rules.json", "kansas_city_ks")  # type: ignore[return-value]


def all_kck_applications() -> list[dict[str, Any]]:
    return list(load_kck_application_catalog().get("applications", []))


def rules_for_application(application: dict[str, Any]) -> list[dict[str, Any]]:
    app_id = application["id"]
    category = application["category"]
    return [
        rule
        for rule in load_kck_permit_rules().get("rules", [])
        if app_id in rule.get("applies_to", []) or category in rule.get("applies_to", [])
    ]


def match_kck_applications(
    scope: dict[str, bool] | None,
    project_type: str | None = None,
) -> list[dict[str, Any]]:
    """Return every official KCK workflow touched by each selected scope flag.

    Applicability uses exact scope arrays only. Vector search and LLMs are deliberately excluded.
    Conditional sibling workflows stay visible as needs_confirmation instead of being discarded.
    """
    active = {key for key, enabled in (scope or {}).items() if enabled}
    normalized_type = " ".join(str(project_type or "").replace("_", " ").casefold().split())
    residential = any(
        marker in normalized_type
        for marker in ("single family", "multifamily residential", "residential")
    )
    incompatible_for_commercial = {
        "residential_building",
        "variance_carport",
        "variance_agricultural_residential",
        "special_use_home_occupation",
        "short_term_rental_admin",
        "short_term_rental_sup",
    }
    incompatible_for_residential = {
        "commercial_building_non_drc",
        "commercial_building_drc",
        "commercial_building_drc_floodplain",
        "variance_commercial_industrial",
    }
    output: list[dict[str, Any]] = []
    for application in all_kck_applications():
        triggered_by = sorted(active.intersection(application.get("scope", [])))
        if not triggered_by:
            continue
        incompatible = (
            not residential and application["id"] in incompatible_for_commercial
        ) or (
            residential and application["id"] in incompatible_for_residential
        )
        direct = any(
            application["id"] in DIRECT_SCOPE_APPLICATIONS.get(scope_key, set())
            for scope_key in triggered_by
        )
        rules = rules_for_application(application)
        output.append(
            {
                **application,
                "requirement_status": (
                    "not_required" if incompatible else "required" if direct else "needs_confirmation"
                ),
                "reason": (
                    "Application use conflicts with the selected project type: "
                    if incompatible
                    else "Direct match for selected scope: "
                    if direct
                    else "Complete conditional candidate for selected scope: "
                ) + ", ".join(key.replace("_", " ") for key in triggered_by),
                "rule_ids": [rule["id"] for rule in rules],
                "source_ids": sorted({source for rule in rules for source in rule.get("source_ids", [])} | {application["source_id"]}),
            }
        )
    return sorted(output, key=lambda item: (item["category"], item["name"], item["id"]))
