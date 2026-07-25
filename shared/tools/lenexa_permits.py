from __future__ import annotations

from typing import Any

from shared.tools.knowledge import load_json


DIRECT_SCOPE_APPLICATIONS = {
    "electrical_work": {"electrical"},
    "mechanical_hvac_work": {"mechanical"},
    "plumbing_work": {"plumbing"},
    "demolition": {"demolition"},
    "solar_battery_generator_ev": {"solar"},
    "grading_land_disturbance": {"land_disturbance"},
    "driveway_sidewalk_row": {"right_of_way"},
}


def all_lenexa_applications() -> list[dict[str, Any]]:
    catalog = load_json("application_catalog.json", "lenexa_ks")
    return list(catalog.get("applications", []))


def load_lenexa_source_registry() -> dict[str, Any]:
    return load_json("source_registry.json", "lenexa_ks")  # type: ignore[return-value]


def load_lenexa_permit_rules() -> dict[str, Any]:
    return load_json("permit_rules.json", "lenexa_ks")  # type: ignore[return-value]


def rules_for_application(application: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        rule
        for rule in load_lenexa_permit_rules().get("rules", [])
        if application["id"] in rule.get("applies_to", [])
        or application["category"] in rule.get("applies_to", [])
    ] or [{
        "id": f"{application['id']}_applicability",
        "applies_to": [application["id"]],
        "rule": f"Resolve whether {application['name']} applies from the cited authority, project facts, and project documents.",
        "source_ids": [application["source_id"]],
    }]


def match_lenexa_applications(
    scope: dict[str, bool] | None,
    project_type: str | None = None,
    answers: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    del project_type
    active = {key for key, enabled in (scope or {}).items() if enabled}
    answers = answers or {}
    output: list[dict[str, Any]] = []
    for application in all_lenexa_applications():
        triggered_by = sorted(active.intersection(application.get("scope", [])))
        if not triggered_by:
            continue
        direct = any(
            application["id"] in DIRECT_SCOPE_APPLICATIONS.get(scope_key, set())
            for scope_key in triggered_by
        )
        trigger_keys = list(application.get("trigger_any", []))
        explicit_key = f"lenexa_{application['id']}_applies"
        trigger_answers = [answers.get(key) for key in trigger_keys]
        explicit_answer = answers.get(explicit_key)
        status = "needs_confirmation"
        if explicit_answer is False or (trigger_keys and all(value is False for value in trigger_answers)):
            status = "not_required"
        elif direct or explicit_answer is True or any(value is True for value in trigger_answers):
            status = "required"
        questions = list(application.get("questions", []))
        for key in trigger_keys:
            if not any(question.get("key") == key for question in questions):
                questions.append({
                    "key": key,
                    "type": "boolean",
                    "label": key.replace("_", " ").capitalize() + "?",
                    "help": f"This fact controls whether {application['name']} applies.",
                })
        if not direct and not questions:
            questions.append({
                "key": explicit_key,
                "type": "boolean",
                "label": f"Does the project require {application['name']}?",
                "help": "Choose no only when confirmed project facts and the cited official workflow exclude it.",
            })
        rules = rules_for_application(application)
        output.append({
            **application,
            "requirement_status": status,
            "reason": (
                "Excluded by confirmed project facts: " if status == "not_required"
                else "Direct match for selected scope: " if status == "required"
                else "Complete conditional candidate for selected scope: "
            ) + ", ".join(key.replace("_", " ") for key in triggered_by),
            "rule_ids": [rule["id"] for rule in rules],
            "source_ids": sorted({application["source_id"], *[source for rule in rules for source in rule.get("source_ids", [])]}),
            "questions": [{**question, "answer": answers.get(question["key"])} for question in questions],
        })
    return sorted(output, key=lambda item: (item["category"], item["name"], item["id"]))
