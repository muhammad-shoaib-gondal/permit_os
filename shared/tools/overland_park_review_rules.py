from __future__ import annotations

import re
from typing import Any

from shared.analysis.rule_coverage import rule_implementation
from shared.analysis.rule_execution import attach_execution_contract
from shared.tools.overland_park_permits import (
    all_overland_park_applications,
    load_overland_park_permit_rules,
    load_overland_park_source_registry,
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _check_type(text: str, rule_id: str = "") -> str:
    token = text.casefold()
    identifier = rule_id.casefold()
    if any(word in token for word in ("before", "after", "expires", "inspection", "issuance", "occupy")):
        return "sequencing"
    if any(word in token for word in ("licensed", "license", "seal", "credential")):
        return "credential"
    if any(word in token for word in (" across ", " agree", "reconcile", "consistent")) or any(word in identifier for word in ("cross_document", "consistency", "coordination")):
        return "cross_document"
    if "dimensional" in identifier or any(word in token for word in ("maximum", "minimum", "fee", "calculate", "threshold", "match")):
        return "value_match"
    return "applicability"


def _expanded(application: dict[str, Any], source_map: dict[str, dict[str, Any]], rule_id: str, title: str, condition: str, check_type: str, source_ids: list[str], severity: str = "blocker", requires_context_standard: bool = False) -> dict[str, Any]:
    links = [{"id": source_id, "title": source_map[source_id]["title"], "url": source_map[source_id]["url"]} for source_id in source_ids if source_id in source_map]
    rule = attach_execution_contract({
        "id": f"overland-park-review-{application['id']}-{rule_id}",
        "category": "zoning" if application["category"] == "Planning and Land Use" else "fire" if application["category"] == "Fire Prevention" else "site" if application["category"] in {"Engineering and Public Works", "Utilities and County", "State and Federal"} else "building",
        "group": application["category"], "rule": title, "condition": condition,
        "severity": severity, "source": " | ".join(link["title"] for link in links),
        "sourceIds": source_ids, "sourceLinks": links, "checkType": check_type,
        "verifiedAt": "2026-07-23", "permitTypes": [application["id"], f"overland_park_{application['id']}"],
        "ruleFamilyIds": [], "requiresContextStandard": requires_context_standard,
        "requiresResolvedStandardValues": requires_context_standard,
    })
    return {**rule, "implementation": rule_implementation(rule)}


def expanded_overland_park_review_rules() -> list[dict[str, Any]]:
    source_map = {item["id"]: item for item in load_overland_park_source_registry().get("sources", [])}
    broad_rules = load_overland_park_permit_rules().get("rules", [])
    output: list[dict[str, Any]] = []
    for application in all_overland_park_applications():
        source_id = application["source_id"]
        output.append(_expanded(application, source_map, "applicability", f"{application['name']} applicability", f"Determine whether {application['name']} is required from the address-derived jurisdiction and zoning, selected scope, permit-specific answers, and project documents. Unknown controlling facts remain not verified.", "applicability", [source_id]))
        for index, document in enumerate(application.get("documents", []), start=1):
            output.append(_expanded(application, source_map, f"document-{index}-{_slug(str(document))}", f"Required evidence: {document}", f"Locate and review the {document} for {application['name']}. Absence, illegibility, incompleteness, or project mismatch is not verified.", "document_presence", [source_id]))
        output.extend([
            _expanded(application, source_map, "identity", "Project identity and scope consistency", "Verify address, parcel or legal description, applicant, scope, and related permit references agree across the application and supporting documents.", "cross_document", [source_id], "major"),
            _expanded(application, source_map, "complete-submission", "Complete application package", f"Verify the {application['name']} application contains every required field, attachment, authorization, signature, fee, and permit-specific item identified by the cited authority.", "document_presence", [source_id]),
            _expanded(application, source_map, "issuance-before-work", "Approval before regulated activity", f"Verify {application['name']} is issued and effective before regulated work, occupancy, operation, event, or disturbance begins.", "sequencing", [source_id]),
            _expanded(application, source_map, "approved-scope", "Work matches approved scope and conditions", f"Compare the proposed activity with the issued {application['name']}, approved plans, limitations, and every condition of approval.", "cross_document", [source_id]),
            _expanded(application, source_map, "closeout", "Inspections, closeout, and continuing validity", f"Verify every inspection, test, acceptance, correction, expiration, renewal, and continuing condition required for {application['name']}.", "sequencing", [source_id]),
        ])
        credential_docs = [str(document) for document in application.get("documents", []) if any(token in str(document).casefold() for token in ("license", "licensed", "seal", "surveyor", "contractor"))]
        if credential_docs:
            output.append(_expanded(application, source_map, "credentials", "Required Kansas and Johnson County credentials", "Verify current credentials applicable to: " + ", ".join(credential_docs) + ".", "credential", [source_id]))
        for broad in broad_rules:
            if application["id"] not in broad.get("applies_to", []) and application["category"] not in broad.get("applies_to", []):
                continue
            source_ids = list(dict.fromkeys([*broad.get("source_ids", []), source_id]))
            output.append(_expanded(application, source_map, f"official-{broad['id']}", broad["id"].replace("_", " ").title(), broad["rule"], _check_type(broad["rule"], broad["id"]), source_ids, "major", broad["id"] == "planning_dimensional"))
    return output
