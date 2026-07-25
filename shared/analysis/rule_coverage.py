from __future__ import annotations

from typing import Any


SUPPORTED_EVALUATORS = {
    "project_fact_resolver",
    "document_inventory",
    "evidence_grounded_value_comparator",
    "evidence_grounded_cross_document_comparator",
    "credential_evidence_verifier",
    "record_timeline_verifier",
}

EVIDENCE_PROVIDERS = {
    "project_record": ["estatepermit_project_record"],
    "project_document": ["uploaded_project_document"],
    "authoritative_standard": [
        "estatepermit_verified_catalog",
        "estatepermit_authoritative_context",
        "uploaded_official_approval_record",
    ],
    "authoritative_registry": [
        "kcmo_contractor_directory",
        "kansas_professional_license_search",
        "kansas_fire_marshal_registry",
        "kansas_asbestos_registry",
        "kck_contractor_licensing",
        "johnson_county_contractor_licensing",
        "lenexa_business_license",
        "uploaded_official_license_record",
    ],
    "dated_status_record": [
        "kcmo_open_data",
        "uploaded_official_status_record",
    ],
}

KNOWN_REGISTRY_PROVIDERS = {
    "kcmo_contractor_directory",
    "missouri_professional_license_search",
    "missouri_elevator_registry",
    "missouri_asbestos_registry",
    "kc_water_approved_tester_registry",
    "national_board_registry",
    "manufacturer_or_federal_credential",
    "uploaded_official_license_record",
    "kansas_professional_license_search",
    "kansas_fire_marshal_registry",
    "kansas_asbestos_registry",
    "kck_contractor_licensing",
    "johnson_county_contractor_licensing",
    "lenexa_business_license",
}


def rule_implementation(rule: dict[str, Any]) -> dict[str, Any]:
    execution = rule.get("execution") or {}
    issues: list[str] = []
    evaluator = str(execution.get("evaluator") or "")
    if evaluator not in SUPPORTED_EVALUATORS:
        issues.append("unsupported evaluator")
    if not rule.get("condition"):
        issues.append("missing review requirement")
    if not rule.get("source"):
        issues.append("missing citation")
    if not rule.get("sourceIds") or not rule.get("sourceLinks"):
        issues.append("missing resolved official source")
    if not execution.get("requiredInputs"):
        issues.append("missing input contract")
    requirements = execution.get("evidenceRequirements") or []
    if not requirements:
        issues.append("missing evidence contract")
    required_types = {
        str(source_type)
        for requirement in requirements
        for source_type in requirement.get("anyOf", [])
    }
    unknown_types = required_types - EVIDENCE_PROVIDERS.keys()
    if unknown_types:
        issues.append(f"missing evidence provider: {', '.join(sorted(unknown_types))}")
    required_registry_providers = {
        str(provider)
        for requirement in requirements
        if "authoritative_registry" in requirement.get("anyOf", [])
        for provider in requirement.get("providers", [])
    }
    if "authoritative_registry" in required_types and not required_registry_providers:
        issues.append("credential rule does not identify accepted registries")
    unknown_registry_providers = required_registry_providers - KNOWN_REGISTRY_PROVIDERS
    if unknown_registry_providers:
        issues.append(
            f"unknown registry provider: {', '.join(sorted(unknown_registry_providers))}"
        )
    if execution.get("passRequiresEvidence") is not True:
        issues.append("pass is not evidence-gated")
    if execution.get("missingOutcome") != "warn":
        issues.append("missing evidence does not produce a warning")

    return {
        "status": "complete" if not issues else "incomplete",
        "issues": issues,
        "evaluator": evaluator,
        "requiredEvidence": sorted(required_types),
        "providers": {
            source_type: EVIDENCE_PROVIDERS[source_type]
            for source_type in sorted(required_types)
            if source_type in EVIDENCE_PROVIDERS
        },
        "acceptedRegistryProviders": sorted(required_registry_providers),
        "unavailableEvidenceOutcome": "not_verified",
    }


def catalog_implementation_report(rules: list[dict[str, Any]]) -> dict[str, Any]:
    entries = [
        {
            "id": rule.get("id"),
            "permitType": rule.get("permitType")
            or ((rule.get("permitTypes") or [None])[0]),
            **rule_implementation(rule),
        }
        for rule in rules
    ]
    incomplete = [entry for entry in entries if entry["status"] != "complete"]
    return {
        "total": len(entries),
        "complete": len(entries) - len(incomplete),
        "incomplete": len(incomplete),
        "entries": entries,
    }
