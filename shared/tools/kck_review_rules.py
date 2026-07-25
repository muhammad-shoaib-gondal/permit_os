from __future__ import annotations

import re
from typing import Any

from shared.analysis.rule_coverage import rule_implementation
from shared.analysis.rule_execution import attach_execution_contract
from shared.tools.kck_permits import (
    all_kck_applications,
    load_kck_permit_rules,
    load_kck_source_registry,
)


_CATEGORY_GROUPS = {
    "Building and Trade": "building",
    "Planning and Land Use": "zoning",
    "Public Works and Utilities": "site",
    "Fire Prevention": "fire",
    "Health and Environmental": "site",
    "State and Federal": "site",
}

_GENERIC_ALIASES = {
    "residential_building": ["building_permit"],
    "commercial_building_non_drc": ["building_permit"],
    "commercial_building_drc": ["building_permit"],
    "commercial_building_drc_floodplain": ["building_permit"],
    "phased_building_approval": ["building_permit"],
    "electrical": ["electrical"],
    "mechanical": ["mechanical"],
    "plumbing": ["plumbing"],
    "demolition": ["demolition"],
    "fire_sprinkler": ["fire_sprinkler", "fire_protection"],
    "fire_alarm": ["fire_alarm", "fire_protection"],
    "certificate_of_occupancy": ["certificate_of_occupancy"],
    "sign_incidental": ["sign"],
    "sign_flag": ["sign"],
    "sign_attached": ["sign"],
    "sign_detached": ["sign"],
    "billboard_under_300": ["sign"],
    "billboard_300_or_more": ["sign"],
    "sanitary_sewer_tap": ["utility_service"],
    "sewer_line_row": ["utility_service"],
    "sewer_abandonment": ["utility_service"],
    "bpu_water_service": ["utility_service"],
    "bpu_electric_service": ["utility_service"],
    "bpu_disconnect": ["utility_service"],
    "bpu_temporary_service": ["utility_service"],
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _source_links(source_ids: list[str], source_map: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "id": source_id,
            "title": str(source_map[source_id]["title"]),
            "url": str(source_map[source_id]["url"]),
        }
        for source_id in source_ids
        if source_id in source_map
    ]


def _check_type(text: str, rule_id: str = "") -> str:
    token = text.casefold()
    identifier = rule_id.casefold()
    if any(word in token for word in ("before", "after", "expires", "inspection", "issuance", "approval")):
        return "sequencing"
    if any(word in token for word in ("licensed", "registered", "seal", "contractor license")):
        return "credential"
    if any(
        word in token for word in (" across ", " agree", "reconcile", "consistent")
    ) or any(word in identifier for word in ("cross_document", "crossdoc", "coordination")):
        return "cross_document"
    if "dimensional" in identifier or any(word in token for word in ("match", "maximum", "minimum", "fee", "dimensions", "calculate", "calculation", "threshold")):
        return "value_match"
    return "applicability"


def _expanded_rule(
    *,
    rule_id: str,
    title: str,
    condition: str,
    check_type: str,
    application: dict[str, Any],
    source_ids: list[str],
    source_map: dict[str, dict[str, Any]],
    severity: str = "blocker",
    requires_context_standard: bool = False,
) -> dict[str, Any]:
    source_links = _source_links(source_ids, source_map)
    group = _CATEGORY_GROUPS.get(application["category"], "building")
    permit_types = {
        application["id"],
        f"kck_{application['id']}",
        *_GENERIC_ALIASES.get(application["id"], []),
    }
    if application["category"] == "Planning and Land Use":
        permit_types.add("planning_entitlement")
    expanded = attach_execution_contract(
        {
            "id": f"kck-review-{application['id']}-{rule_id}",
            "category": group,
            "group": group,
            "rule": title,
            "condition": condition,
            "severity": severity,
            "source": " | ".join(link["title"] for link in source_links),
            "sourceLinks": source_links,
            "sourceIds": source_ids,
            "checkType": check_type,
            "verifiedAt": "2026-07-22",
            "permitTypes": sorted(permit_types),
            "ruleFamilyIds": [],
            "requiresContextStandard": requires_context_standard,
            "requiresResolvedStandardValues": requires_context_standard,
        }
    )
    return {**expanded, "implementation": rule_implementation(expanded)}


def expanded_kck_review_rules() -> list[dict[str, Any]]:
    registry = load_kck_source_registry()
    source_map = {item["id"]: item for item in registry.get("sources", [])}
    broad_rules = load_kck_permit_rules().get("rules", [])
    output: list[dict[str, Any]] = []

    for application in all_kck_applications():
        source_id = application["source_id"]
        output.append(
            _expanded_rule(
                rule_id="applicability",
                title=f"{application['name']} applicability",
                condition=(
                    f"Determine whether {application['name']} is required from the project scope, "
                    "address-derived jurisdiction and zoning records, permit-specific answers, and uploaded documents. "
                    "Do not classify it as not required while a controlling fact is unknown."
                ),
                check_type="applicability",
                application=application,
                source_ids=[source_id],
                source_map=source_map,
            )
        )

        for rule_id, title, condition, check_type in (
            (
                "complete-submission",
                "Complete application package",
                f"Verify the {application['name']} application contains every required field, attachment, owner authorization, signature, fee, and workflow-specific item identified by the cited authority. Incomplete evidence is not verified.",
                "document_presence",
            ),
            (
                "issuance-before-work",
                "Approval before regulated activity",
                f"Verify {application['name']} is issued and effective before the regulated construction, occupancy, operation, disturbance, discharge, or other activity begins; an application or payment receipt is not approval.",
                "sequencing",
            ),
            (
                "approved-scope",
                "Work matches approved scope and conditions",
                f"Compare the proposal with the issued {application['name']}, accepted plans, limitations, and every condition. Unapproved deviations are not verified.",
                "cross_document",
            ),
            (
                "closeout",
                "Inspections, closeout, and continuing validity",
                f"Verify every inspection, test, acceptance, correction, expiration, renewal, report, and continuing condition required for {application['name']}. Outstanding or expired items are not verified.",
                "sequencing",
            ),
        ):
            output.append(
                _expanded_rule(
                    rule_id=rule_id,
                    title=title,
                    condition=condition,
                    check_type=check_type,
                    application=application,
                    source_ids=[source_id],
                    source_map=source_map,
                    severity="major",
                )
            )

        for index, document in enumerate(application.get("documents", []), start=1):
            output.append(
                _expanded_rule(
                    rule_id=f"document-{index}-{_slug(str(document))}",
                    title=f"Required evidence: {document}",
                    condition=(
                        f"Locate and review the {document} for {application['name']}. "
                        "If it is absent, incomplete, illegible, or belongs to another project, return not verified."
                    ),
                    check_type="document_presence",
                    application=application,
                    source_ids=[source_id],
                    source_map=source_map,
                )
            )

        output.append(
            _expanded_rule(
                rule_id="project-identity-cross-check",
                title="Project identity and scope consistency",
                condition=(
                    "Verify that the address, parcel or legal description when present, owner/applicant, project scope, "
                    "and permit references are consistent across the application and supporting documents."
                ),
                check_type="cross_document",
                application=application,
                source_ids=[source_id],
                source_map=source_map,
                severity="major",
            )
        )

        credential_documents = [
            str(document)
            for document in application.get("documents", [])
            if any(
                token in str(document).casefold()
                for token in ("licensed", "contractor license", "seal", "installer information", "asme")
            )
        ]
        if credential_documents:
            output.append(
                _expanded_rule(
                    rule_id="credential-verification",
                    title="Required professional and contractor credentials",
                    condition=(
                        "Verify current Kansas or Unified Government credentials for: "
                        + ", ".join(credential_documents)
                        + ". A name or seal without verifiable credential evidence is not a pass."
                    ),
                    check_type="credential",
                    application=application,
                    source_ids=[source_id],
                    source_map=source_map,
                )
            )

        matched = [
            rule
            for rule in broad_rules
            if application["id"] in rule.get("applies_to", [])
            or application["category"] in rule.get("applies_to", [])
        ]
        for broad in matched:
            source_ids = list(dict.fromkeys([*broad.get("source_ids", []), source_id]))
            output.append(
                _expanded_rule(
                    rule_id=f"official-{broad['id']}",
                    title=broad["id"].replace("_", " ").title(),
                    condition=broad["rule"],
                    check_type=_check_type(broad["rule"], broad["id"]),
                    application=application,
                    source_ids=source_ids,
                    source_map=source_map,
                    severity="major",
                    requires_context_standard=broad["id"] == "planning_dimensional_design",
                )
            )

    return output
