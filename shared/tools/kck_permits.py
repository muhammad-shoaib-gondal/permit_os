from __future__ import annotations

from typing import Any

from shared.tools.knowledge import load_json


DIRECT_SCOPE_APPLICATIONS = {
    "electrical_work": {"electrical"},
    "mechanical_hvac_work": {"mechanical"},
    "plumbing_work": {"plumbing"},
    "demolition": {"demolition"},
    "grading_land_disturbance": {"land_disturbance"},
    "driveway_sidewalk_row": {"right_of_way"},
}


def load_kck_application_catalog() -> dict[str, Any]:
    base = load_json("application_catalog.json", "kansas_city_ks")
    supplement = load_json("supplemental_application_catalog.json", "kansas_city_ks")
    overrides = {item["id"]: item for item in supplement.get("application_overrides", [])}
    applications = [
        {**item, **overrides.get(item["id"], {})}
        for item in base.get("applications", [])
    ]
    applications.extend(supplement.get("applications", []))
    return {
        **base,
        "snapshot_date": supplement.get("snapshot_date", base.get("snapshot_date")),
        "applications": applications,
    }


def load_kck_source_registry() -> dict[str, Any]:
    base = load_json("source_registry.json", "kansas_city_ks")
    supplement = load_json("supplemental_source_registry.json", "kansas_city_ks")
    sources = {item["id"]: item for item in base.get("sources", [])}
    sources.update({item["id"]: item for item in supplement.get("sources", [])})
    return {
        **base,
        "last_verified": supplement.get("last_verified", base.get("last_verified")),
        "sources": list(sources.values()),
    }


def load_kck_permit_rules() -> dict[str, Any]:
    return load_json("permit_rules.json", "kansas_city_ks")  # type: ignore[return-value]


def all_kck_applications() -> list[dict[str, Any]]:
    return list(load_kck_application_catalog().get("applications", []))


def rules_for_application(application: dict[str, Any]) -> list[dict[str, Any]]:
    app_id = application["id"]
    category = application["category"]
    matched = [
        rule
        for rule in load_kck_permit_rules().get("rules", [])
        if app_id in rule.get("applies_to", []) or category in rule.get("applies_to", [])
    ]
    if matched:
        return matched
    return [
        {
            "id": f"{app_id}_applicability",
            "applies_to": [app_id],
            "rule": (
                f"Resolve whether {application['name']} applies from the cited authority, "
                "project facts, and uploaded project documents."
            ),
            "source_ids": [application["source_id"]],
        }
    ]


def match_kck_applications(
    scope: dict[str, bool] | None,
    project_type: str | None = None,
    answers: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return every official KCK workflow touched by each selected scope flag.

    Applicability uses exact scope arrays only. Vector search and LLMs are deliberately excluded.
    Conditional sibling workflows stay visible as needs_confirmation instead of being discarded.
    """
    active = {key for key, enabled in (scope or {}).items() if enabled}
    answers = answers or {}
    normalized_type = " ".join(str(project_type or "").replace("_", " ").casefold().split())
    explicitly_residential = any(
        marker in normalized_type
        for marker in ("single family", "multifamily residential", "residential only")
    ) and "mixed" not in normalized_type
    explicitly_commercial = any(
        marker in normalized_type
        for marker in ("commercial", "industrial", "office", "retail", "warehouse")
    ) and "mixed" not in normalized_type
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
            explicitly_commercial and application["id"] in incompatible_for_commercial
        ) or (
            explicitly_residential and application["id"] in incompatible_for_residential
        )
        direct = any(
            application["id"] in DIRECT_SCOPE_APPLICATIONS.get(scope_key, set())
            for scope_key in triggered_by
        )
        trigger_keys = list(application.get("trigger_any", []))
        explicit_key = f"kck_{application['id']}_applies"
        explicit_answer = answers.get(explicit_key)
        trigger_answers = [answers.get(key) for key in trigger_keys]
        triggered = any(value is True for value in trigger_answers)
        all_triggers_excluded = bool(trigger_keys) and all(
            value is False for value in trigger_answers
        )
        rules = rules_for_application(application)
        questions = list(application.get("questions", []))
        if not direct and not questions:
            questions.append(
                {
                    "key": explicit_key,
                    "type": "boolean",
                    "label": f"Does the project require {application['name']}?",
                    "help": (
                        "Use the cited official workflow and uploaded project documents. "
                        "Choose no only when the project facts exclude it."
                    ),
                }
            )
        status = "needs_confirmation"
        if incompatible or explicit_answer is False or all_triggers_excluded:
            status = "not_required"
        elif direct or explicit_answer is True or triggered:
            status = "required"
        output.append(
            {
                **application,
                "requirement_status": status,
                "reason": (
                    "Application use conflicts with the selected project type: "
                    if incompatible
                    else "Excluded by confirmed project facts: "
                    if status == "not_required"
                    else "Direct match for selected scope: "
                    if status == "required"
                    else "Complete conditional candidate for selected scope: "
                ) + ", ".join(key.replace("_", " ") for key in triggered_by),
                "rule_ids": [rule["id"] for rule in rules],
                "source_ids": sorted({source for rule in rules for source in rule.get("source_ids", [])} | {application["source_id"]}),
                "questions": [
                    {**question, "answer": answers.get(question["key"])}
                    for question in questions
                ],
            }
        )
    return sorted(output, key=lambda item: (item["category"], item["name"], item["id"]))
