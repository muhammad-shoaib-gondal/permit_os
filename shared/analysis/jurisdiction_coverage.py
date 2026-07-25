"""Machine-checkable coverage contract for supported EstatePermit jurisdictions."""

from __future__ import annotations

from collections import Counter
from typing import Any

from shared.tools.kck_permits import (
    all_kck_applications,
    load_kck_source_registry,
    match_kck_applications,
)
from shared.tools.kck_review_rules import expanded_kck_review_rules
from shared.tools.kcmo_approvals import load_approval_catalog
from shared.tools.kcmo_permits import (
    all_applications,
    load_compass_catalog,
    match_kcmo_applications,
)
from shared.tools.kcmo_review_rules import expanded_review_rules
from shared.tools.lenexa_permits import (
    all_lenexa_applications,
    load_lenexa_source_registry,
    match_lenexa_applications,
)
from shared.tools.lenexa_review_rules import expanded_lenexa_review_rules
from shared.tools.overland_park_permits import (
    all_overland_park_applications,
    load_overland_park_source_registry,
    match_overland_park_applications,
)
from shared.tools.overland_park_review_rules import expanded_overland_park_review_rules


ALL_SCOPE = {
    "new_construction": True,
    "addition": True,
    "alteration": True,
    "repair": True,
    "demolition": True,
    "structural_work": True,
    "electrical_work": True,
    "plumbing_work": True,
    "mechanical_hvac_work": True,
    "fire_alarm_sprinkler_work": True,
    "signs": True,
    "change_use_occupancy": True,
    "grading_land_disturbance": True,
    "driveway_sidewalk_row": True,
    "solar_battery_generator_ev": True,
    "water_sewer_connections": True,
}


def _rule_issues(rules: list[dict[str, Any]], expected_targets: set[str]) -> list[str]:
    issues: list[str] = []
    ids = [str(rule.get("id") or "") for rule in rules]
    if len(ids) != len(set(ids)):
        issues.append("duplicate review-rule IDs")
    targets = {
        str(permit_type)
        for rule in rules
        for permit_type in rule.get("permitTypes", [])
    }
    missing_targets = sorted(expected_targets - targets)
    if missing_targets:
        issues.append(f"workflows without review rules: {', '.join(missing_targets)}")
    for rule in rules:
        if not rule.get("sourceLinks"):
            issues.append(f"rule without source link: {rule.get('id')}")
        if rule.get("implementation", {}).get("status") != "complete":
            issues.append(f"incomplete rule implementation: {rule.get('id')}")
        execution = rule.get("execution", {})
        if execution.get("evaluator") == "unsupported":
            issues.append(f"unsupported evaluator: {rule.get('id')}")
        if execution.get("missingOutcome") != "warn":
            issues.append(f"non-fail-closed rule: {rule.get('id')}")
    return list(dict.fromkeys(issues))


def _application_issues(
    applications: list[dict[str, Any]],
    source_ids: set[str],
) -> list[str]:
    issues: list[str] = []
    ids = [str(application.get("id")) for application in applications]
    if len(ids) != len(set(ids)):
        issues.append("duplicate workflow IDs")
    for application in applications:
        app_id = application.get("id")
        if application.get("source_id") not in source_ids:
            issues.append(f"workflow without registered source: {app_id}")
        if not application.get("scope"):
            issues.append(f"workflow without a scope route: {app_id}")
        if not application.get("documents"):
            issues.append(f"workflow without document requirements: {app_id}")
    return issues


def _pack_report(
    *,
    workflow_count: int,
    selected_count: int,
    rules: list[dict[str, Any]],
    expected_targets: set[str],
    issues: list[str],
) -> dict[str, Any]:
    target_counts = Counter(
        permit_type
        for rule in rules
        for permit_type in rule.get("permitTypes", [])
        if permit_type in expected_targets
    )
    return {
        "workflowCount": workflow_count,
        "selectedByAllScopeCount": selected_count,
        "reviewRuleCount": len(rules),
        "coveredWorkflowCount": len(target_counts),
        "minimumRulesPerWorkflow": min(target_counts.values()) if target_counts else 0,
        "issues": issues,
        "complete": not issues and workflow_count == selected_count == len(expected_targets),
    }


def build_jurisdiction_coverage_report() -> dict[str, Any]:
    kcmo_permits = all_applications("permit")
    kcmo_plans = all_applications("plan")
    kcmo_exact = [*kcmo_permits, *kcmo_plans]
    kcmo_approvals = load_approval_catalog()["approvals"]
    kcmo_targets = {
        *(str(approval["id"]) for approval in kcmo_approvals),
        *(
            f"compass_{application['application_kind']}_{application['id']}"
            for application in kcmo_exact
        ),
    }
    kcmo_rules = expanded_review_rules()
    kcmo_selected = match_kcmo_applications(ALL_SCOPE, "mixed_use")
    kcmo_issues = _rule_issues(kcmo_rules, kcmo_targets)
    if len(kcmo_exact) != len(kcmo_selected):
        kcmo_issues.append("not every Compass workflow is returned by the all-scope fixture")
    if not all(application.get("questions") for application in kcmo_selected):
        kcmo_issues.append("Compass workflow without a user-facing applicability question")
    compass_catalog = load_compass_catalog()
    if len(kcmo_permits) != len(compass_catalog["permit_applications"]):
        kcmo_issues.append("permit snapshot count mismatch")
    if len(kcmo_plans) != len(compass_catalog["plan_applications"]):
        kcmo_issues.append("plan snapshot count mismatch")

    kck_apps = all_kck_applications()
    kck_sources = {
        str(source["id"]) for source in load_kck_source_registry().get("sources", [])
    }
    kck_targets = {f"kck_{application['id']}" for application in kck_apps}
    kck_rules = expanded_kck_review_rules()
    kck_selected = match_kck_applications(ALL_SCOPE, "mixed_use")
    kck_issues = [
        *_application_issues(kck_apps, kck_sources),
        *_rule_issues(kck_rules, kck_targets),
    ]
    if not all(
        item["requirement_status"] == "required" or item.get("questions")
        for item in kck_selected
    ):
        kck_issues.append("conditional KCK workflow without a user-facing question")

    lenexa_apps = all_lenexa_applications()
    lenexa_sources = {
        str(source["id"]) for source in load_lenexa_source_registry().get("sources", [])
    }
    lenexa_targets = {f"lenexa_{application['id']}" for application in lenexa_apps}
    lenexa_rules = expanded_lenexa_review_rules()
    lenexa_selected = match_lenexa_applications(ALL_SCOPE, "mixed_use")
    lenexa_issues = [
        *_application_issues(lenexa_apps, lenexa_sources),
        *_rule_issues(lenexa_rules, lenexa_targets),
    ]
    if not all(
        item["requirement_status"] == "required" or item.get("questions")
        for item in lenexa_selected
    ):
        lenexa_issues.append("conditional Lenexa workflow without a user-facing question")

    overland_park_apps = all_overland_park_applications()
    overland_park_sources = {
        str(source["id"]) for source in load_overland_park_source_registry().get("sources", [])
    }
    overland_park_targets = {f"overland_park_{application['id']}" for application in overland_park_apps}
    overland_park_rules = expanded_overland_park_review_rules()
    overland_park_selected = match_overland_park_applications(ALL_SCOPE, "mixed_use")
    overland_park_issues = [
        *_application_issues(overland_park_apps, overland_park_sources),
        *_rule_issues(overland_park_rules, overland_park_targets),
    ]
    if not all(
        item["requirement_status"] == "required" or item.get("questions")
        for item in overland_park_selected
    ):
        overland_park_issues.append("conditional Overland Park workflow without a user-facing question")

    jurisdictions = {
        "kansas_city_mo": _pack_report(
            workflow_count=len(kcmo_targets),
            selected_count=len(kcmo_selected) + len(kcmo_approvals),
            rules=kcmo_rules,
            expected_targets=kcmo_targets,
            issues=kcmo_issues,
        ),
        "kansas_city_ks": _pack_report(
            workflow_count=len(kck_apps),
            selected_count=len(kck_selected),
            rules=kck_rules,
            expected_targets=kck_targets,
            issues=kck_issues,
        ),
        "lenexa_ks": _pack_report(
            workflow_count=len(lenexa_apps),
            selected_count=len(lenexa_selected),
            rules=lenexa_rules,
            expected_targets=lenexa_targets,
            issues=lenexa_issues,
        ),
        "overland_park_ks": _pack_report(
            workflow_count=len(overland_park_apps),
            selected_count=len(overland_park_selected),
            rules=overland_park_rules,
            expected_targets=overland_park_targets,
            issues=overland_park_issues,
        ),
    }
    return {
        "contract": "official-source snapshot coverage with fail-closed unknowns",
        "jurisdictions": jurisdictions,
        "complete": all(item["complete"] for item in jurisdictions.values()),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(build_jurisdiction_coverage_report(), indent=2))
