from __future__ import annotations

from typing import Any

from shared.tools.knowledge import load_json
from shared.analysis.rule_execution import attach_execution_contract
from shared.analysis.rule_coverage import rule_implementation
from shared.tools.kcmo_permits import all_applications, load_permit_rules, rule_family_for_category


_SITE_PERMITS = {
    "land_disturbance",
    "modnr_construction_stormwater",
    "stormwater_management",
    "row_excavation",
    "sidewalk_curb_driveway",
    "traffic_lane_sidewalk_closure",
    "streetcar_track_access",
    "encroachment_vault",
    "hauling_oversize",
    "crane_erection",
    "dust_control",
    "asbestos_neshap",
    "demolition",
    "domestic_water_service",
    "fire_water_service",
    "sanitary_sewer_connection",
    "storm_sewer_connection",
    "backflow_prevention",
    "water_main_extension",
    "industrial_pretreatment",
}

_FIRE_PERMITS = {
    "fire_sprinkler",
    "fire_alarm",
    "standpipe",
    "fire_pump",
    "errc_bda_das",
    "smoke_control",
    "kitchen_hood_suppression",
    "hazardous_materials_operational",
}

_ZONING_PERMITS = {
    "zoning_verification",
    "certificate_appropriateness",
    "ur_development_plan",
    "platting_lot_consolidation",
}


def load_review_rule_catalog() -> dict[str, Any]:
    return load_json("review_rule_catalog.json", "kansas_city_mo")  # type: ignore[return-value]


def load_external_assessment_overlay() -> dict[str, Any]:
    return load_json(
        "external_assessment_rule_overlay.json", "kansas_city_mo"
    )  # type: ignore[return-value]


def _category_for_permit(permit_id: str) -> str:
    if permit_id in _ZONING_PERMITS:
        return "zoning"
    if permit_id in _SITE_PERMITS:
        return "site"
    if permit_id in _FIRE_PERMITS:
        return "fire"
    return "building"


def _exact_check_type(text: str) -> str:
    value = text.casefold()
    if any(token in value for token in ("before", "after", "until", "sequence", "proceed", "issued", "recorded")):
        return "sequencing"
    if any(token in value for token in ("license", "licensed", "seal", "surveyor", "professional")):
        return "credential"
    if any(token in value for token in ("agree", "match", "reconcile", "consistent", "linked")):
        return "cross_document"
    if any(token in value for token in ("maximum", "minimum", "calculate", "size", "dimension", "threshold")):
        return "value_match"
    return "applicability"


def _exact_compass_rules(source_map: dict[str, dict[str, Any]], verified_at: str) -> list[dict[str, Any]]:
    permit_rules = load_permit_rules()
    global_rules = permit_rules.get("global_rules", [])
    output: list[dict[str, Any]] = []
    for kind in ("permit", "plan"):
        for application in all_applications(kind):
            family = rule_family_for_category(application["category"])
            if not family:
                continue
            target = f"compass_{kind}_{application['id']}"
            rows: list[tuple[str, str, str, list[str]]] = [
                (
                    "applicability",
                    f"{application['name']} applicability",
                    f"Determine whether the exact CompassKC {kind} application '{application['name']}' applies from project type, scope, location, related records, and permit-specific facts. Unknown facts remain not verified.",
                    ["compass_application_assistant"],
                ),
                (
                    "identity",
                    "Exact CompassKC route and project identity",
                    f"Verify application ID {application['id']}, category '{application['category']}', address, parcel, applicant, scope, and related records all identify the same project and requested workflow.",
                    ["compass_application_assistant"],
                ),
            ]
            rows.extend(
                (f"global-{rule['id'].casefold()}", rule["id"], rule["rule"], list(rule["sources"]))
                for rule in global_rules
            )
            rows.extend(
                (f"family-{index}", f"{family['id'].replace('_', ' ').title()} rule {index}", text, list(family["sources"]))
                for index, text in enumerate(family.get("rules", []), start=1)
            )
            rows.extend(
                (f"document-{index}", f"Required evidence: {document}", f"Locate and verify the {document} for {application['name']}; missing, incomplete, illegible, stale, or mismatched evidence is not verified.", list(family["sources"]))
                for index, document in enumerate(family.get("required_documents", []), start=1)
            )
            for rule_id, title, condition, source_ids in rows:
                links = [
                    {"id": source_id, "title": source_map[source_id]["title"], "url": source_map[source_id]["url"]}
                    for source_id in source_ids
                    if source_id in source_map
                ]
                check_type = "document_presence" if rule_id.startswith("document-") else "cross_document" if rule_id == "identity" else _exact_check_type(condition)
                requires_context_standard = check_type == "value_match" and (
                    application["category"].startswith("Planning")
                    or application["category"] == "Zoning"
                )
                expanded = attach_execution_contract({
                    "id": f"kcmo-compass-{kind}-{application['id']}-{rule_id}",
                    "category": "zoning" if application["category"].startswith("Planning") or application["category"] == "Zoning" else "site" if application["category"].startswith(("Street", "Water", "City Infrastructure")) else "building",
                    "group": application["category"],
                    "rule": title,
                    "condition": condition,
                    "severity": "blocker",
                    "source": " | ".join(link["title"] for link in links),
                    "sourceLinks": links,
                    "sourceIds": source_ids,
                    "checkType": check_type,
                    "verifiedAt": verified_at,
                    "permitTypes": [target],
                    "ruleFamilyIds": [family["id"]],
                    "requiresContextStandard": requires_context_standard,
                    "requiresResolvedStandardValues": requires_context_standard,
                })
                output.append({**expanded, "implementation": rule_implementation(expanded)})
    return output


def expanded_review_rules() -> list[dict[str, Any]]:
    catalog = load_review_rule_catalog()
    registry = load_json("source_registry.json", "kansas_city_mo")
    source_map = {source["id"]: source for source in registry.get("sources", [])}
    shared_sets = catalog.get("shared_rule_sets", {})
    output: list[dict[str, Any]] = []

    for permit in catalog.get("permits", []):
        permit_id = permit["permit_id"]
        permit_name = permit.get("permit_name") or permit_id.replace("_", " ").title()
        rules: list[dict[str, Any]] = [
            {
                "id": "workflow-applicability",
                "title": f"{permit_name} applicability",
                "requirement": (
                    f"Determine whether {permit_name} applies from the project address, zoning and overlays, "
                    "scope, permit-specific answers, related records, and project documents. Unknown controlling "
                    "facts remain not verified and may not be treated as not required."
                ),
                "severity": "blocker",
                "source_ids": ["compass_application_assistant"],
                "citation": "CompassKC application and related-record workflow",
                "check_type": "applicability",
            },
            {
                "id": "workflow-complete-submission",
                "title": "Complete application package",
                "requirement": (
                    f"Verify the {permit_name} package contains every required field, attachment, authorization, "
                    "signature, fee item, and workflow-specific submittal identified by the cited authority."
                ),
                "severity": "blocker",
                "source_ids": ["compass_application_assistant"],
                "citation": "CompassKC application workflow",
                "check_type": "document_presence",
            },
            {
                "id": "workflow-issuance-before-work",
                "title": "Issued approval before regulated activity",
                "requirement": (
                    f"Verify {permit_name} is issued and effective before its regulated construction, occupancy, "
                    "operation, disturbance, discharge, or right-of-way activity begins. An application or fee "
                    "receipt is not an issued approval."
                ),
                "severity": "blocker",
                "source_ids": ["compass_application_assistant"],
                "citation": "CompassKC permit issuance and related-record workflow",
                "check_type": "sequencing",
            },
            {
                "id": "workflow-approved-scope",
                "title": "Work matches approved scope and conditions",
                "requirement": (
                    f"Compare the proposed work with the issued {permit_name}, accepted plans, limitations, and all "
                    "conditions of approval. Unapproved deviations remain not verified."
                ),
                "severity": "blocker",
                "source_ids": ["compass_application_assistant"],
                "citation": "CompassKC approved-document and related-record workflow",
                "check_type": "cross_document",
            },
            {
                "id": "workflow-closeout",
                "title": "Inspections, closeout, and continuing validity",
                "requirement": (
                    f"Verify every inspection, test, acceptance, correction, expiration, renewal, reporting, and "
                    f"continuing condition required for {permit_name}. Outstanding or expired items are not verified."
                ),
                "severity": "major",
                "source_ids": ["compass_application_assistant"],
                "citation": "CompassKC inspections and permit-status workflow",
                "check_type": "sequencing",
            },
        ]
        for set_id in permit.get("include_sets", []):
            rules.extend(shared_sets.get(set_id, []))
        rules.extend(permit.get("rules", []))

        for rule in rules:
            source_links = [
                {
                    "id": source_id,
                    "title": source_map[source_id]["title"],
                    "url": source_map[source_id]["url"],
                }
                for source_id in rule.get("source_ids", [])
                if source_id in source_map
            ]
            requires_context_standard = (
                permit_id in _ZONING_PERMITS and rule["check_type"] == "value_match"
            )
            expanded = attach_execution_contract({
                    "id": f"kcmo-review-{permit_id}-{rule['id']}",
                    "category": _category_for_permit(permit_id),
                    "group": _category_for_permit(permit_id),
                    "rule": rule["title"],
                    "condition": rule["requirement"],
                    "severity": rule.get("severity", "blocker"),
                    "source": rule["citation"],
                    "sourceLinks": source_links,
                    "sourceIds": rule.get("source_ids", []),
                    "checkType": rule["check_type"],
                    "verifiedAt": catalog["verified_at"],
                    "permitTypes": [permit_id],
                    "ruleFamilyIds": [],
                    "requiresContextStandard": requires_context_standard,
                    "requiresResolvedStandardValues": requires_context_standard,
                })
            output.append({**expanded, "implementation": rule_implementation(expanded)})

    overlay = load_external_assessment_overlay()
    executable = [
        rule
        for rule in overlay.get("rules", [])
        if rule.get("disposition") in {"active", "corrected"}
    ]
    executable.sort(key=lambda rule: rule.get("review_phase") == "cross_permit_final")
    for rule in executable:
        source_links = [
            {
                "id": source_id,
                "title": source_map[source_id]["title"],
                "url": source_map[source_id]["url"],
            }
            for source_id in rule.get("source_ids", [])
            if source_id in source_map
        ]
        requires_context_standard = (
            rule["permit_id"] == "zoning_verification"
            and rule["check_type"] == "value_match"
        )
        expanded = attach_execution_contract({
            "id": f"kcmo-assessment-{rule['external_id'].lower()}",
            "category": _category_for_permit(rule["permit_id"]),
            "group": _category_for_permit(rule["permit_id"]),
            "rule": rule["title"],
            "condition": rule["requirement"],
            "severity": rule.get("severity", "blocker"),
            "source": rule["citation"],
            "sourceLinks": source_links,
            "sourceIds": rule.get("source_ids", []),
            "checkType": rule["check_type"],
            "verifiedAt": overlay["verified_at"],
            "permitTypes": [rule["permit_id"]],
            "ruleFamilyIds": [],
            "externalAssessmentId": rule["external_id"],
            "auditStatus": rule["disposition"],
            "reviewPhase": rule.get("review_phase", "permit"),
            "requiresContextStandard": requires_context_standard,
        })
        output.append({**expanded, "implementation": rule_implementation(expanded)})
    output.extend(_exact_compass_rules(source_map, catalog["verified_at"]))
    return output


def review_questions_for_permit(permit_id: str) -> list[dict[str, Any]]:
    catalog = load_review_rule_catalog()
    shared_sets = catalog.get("shared_rule_sets", {})
    permit = next(
        (item for item in catalog.get("permits", []) if item["permit_id"] == permit_id),
        None,
    )
    if permit is None:
        return []

    rules: list[dict[str, Any]] = []
    for set_id in permit.get("include_sets", []):
        rules.extend(shared_sets.get(set_id, []))
    rules.extend(permit.get("rules", []))

    questions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in rules:
        question = rule.get("question")
        if not question or question["key"] in seen:
            continue
        seen.add(question["key"])
        questions.append({**question, "ruleId": rule["id"], "ruleTitle": rule["title"]})
    return questions
