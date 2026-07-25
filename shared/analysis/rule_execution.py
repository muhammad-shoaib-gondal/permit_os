from __future__ import annotations

from typing import Any


EXECUTION_CONTRACTS: dict[str, dict[str, Any]] = {
    "applicability": {
        "evaluator": "project_fact_resolver",
        "requiredInputs": ["project_facts"],
        "evidenceRequirements": [{"anyOf": ["project_record", "project_document"], "minimum": 1}],
        "passRequiresEvidence": True,
        "missingOutcome": "warn",
    },
    "document_presence": {
        "evaluator": "document_inventory",
        "requiredInputs": ["document_inventory", "document_content"],
        "evidenceRequirements": [{"anyOf": ["project_document"], "minimum": 1}],
        "passRequiresEvidence": True,
        "missingOutcome": "warn",
    },
    "value_match": {
        "evaluator": "evidence_grounded_value_comparator",
        "requiredInputs": ["authoritative_standard", "document_values"],
        "evidenceRequirements": [
            {"anyOf": ["authoritative_standard"], "minimum": 1},
            {"anyOf": ["project_document"], "minimum": 1},
        ],
        "passRequiresEvidence": True,
        "missingOutcome": "warn",
    },
    "cross_document": {
        "evaluator": "evidence_grounded_cross_document_comparator",
        "requiredInputs": ["two_or_more_document_values"],
        "evidenceRequirements": [{"anyOf": ["project_document"], "minimum": 2, "distinctDocuments": True}],
        "passRequiresEvidence": True,
        "missingOutcome": "warn",
    },
    "credential": {
        "evaluator": "credential_evidence_verifier",
        "requiredInputs": ["credential_document", "authoritative_registry_when_required"],
        "evidenceRequirements": [
            {"anyOf": ["project_document"], "minimum": 1},
            {"anyOf": ["authoritative_registry"], "minimum": 1},
        ],
        "passRequiresEvidence": True,
        "missingOutcome": "warn",
    },
    "sequencing": {
        "evaluator": "record_timeline_verifier",
        "requiredInputs": ["dated_status_records", "dependency_order"],
        "evidenceRequirements": [
            {"anyOf": ["authoritative_standard"], "minimum": 1},
            {"anyOf": ["dated_status_record"], "minimum": 1},
        ],
        "passRequiresEvidence": True,
        "missingOutcome": "warn",
    },
}


def _credential_providers(rule: dict[str, Any]) -> list[str]:
    searchable = " ".join(
        [
            str(rule.get("id") or ""),
            str(rule.get("rule") or ""),
            str(rule.get("condition") or ""),
            " ".join(str(value) for value in rule.get("sourceIds", [])),
        ]
    ).casefold()
    is_kck_rule = searchable.startswith("kck-") or " kck-review-" in searchable
    is_lenexa_rule = searchable.startswith("lenexa-") or " lenexa-review-" in searchable
    is_overland_park_rule = searchable.startswith("overland-park-") or " overland-park-review-" in searchable
    if is_overland_park_rule and any(
        value in searchable
        for value in ("architect", "engineer", "surveyor", "design professional", "professional seal", "sealed")
    ):
        return ["kansas_professional_license_search", "uploaded_official_license_record"]
    if is_overland_park_rule:
        return ["johnson_county_contractor_licensing", "uploaded_official_license_record"]
    if is_lenexa_rule and any(
        value in searchable
        for value in ("architect", "engineer", "surveyor", "design professional", "professional seal", "sealed")
    ):
        return ["kansas_professional_license_search", "uploaded_official_license_record"]
    if is_lenexa_rule:
        return [
            "johnson_county_contractor_licensing",
            "lenexa_business_license",
            "uploaded_official_license_record",
        ]
    if is_kck_rule and any(
        value in searchable
        for value in (
            "architect",
            "engineer",
            "surveyor",
            "design professional",
            "professional seal",
            "sealed",
        )
    ):
        return ["kansas_professional_license_search", "uploaded_official_license_record"]
    if any(value in searchable for value in ("kansas-licensed", "kansas licensed", "kansas registered")):
        return ["kansas_professional_license_search", "uploaded_official_license_record"]
    if any(value in searchable for value in ("kansas state fire marshal", "ks_elevator", "ks_boiler")):
        return ["kansas_fire_marshal_registry", "uploaded_official_license_record"]
    if "asbestos" in searchable and ("kdhe" in searchable or "kansas" in searchable):
        return ["kansas_asbestos_registry", "uploaded_official_license_record"]
    if "kck-" in searchable and any(
        value in searchable for value in ("licensed contractor", "contractor license", "credential")
    ):
        return ["kck_contractor_licensing", "uploaded_official_license_record"]
    if is_kck_rule:
        return ["kck_contractor_licensing", "uploaded_official_license_record"]
    if any(value in searchable for value in ("architect", "engineer", "surveyor", "professional seal", "design professional")):
        return ["missouri_professional_license_search", "uploaded_official_license_record"]
    if "elevator" in searchable:
        return ["missouri_elevator_registry", "uploaded_official_license_record"]
    if "asbestos" in searchable:
        return ["missouri_asbestos_registry", "uploaded_official_license_record"]
    if "backflow" in searchable:
        return ["kc_water_approved_tester_registry", "uploaded_official_license_record"]
    if "asme" in searchable or "national board" in searchable:
        return ["national_board_registry", "uploaded_official_license_record"]
    if "fcc" in searchable or "manufacturer" in searchable or "listed-system" in searchable:
        return ["manufacturer_or_federal_credential", "uploaded_official_license_record"]
    return ["kcmo_contractor_directory", "uploaded_official_license_record"]


def execution_contract(check_type: str) -> dict[str, Any]:
    contract = EXECUTION_CONTRACTS.get(check_type)
    if contract is None:
        return {
            "evaluator": "unsupported",
            "requiredInputs": [],
            "evidenceRequirements": [],
            "passRequiresEvidence": True,
            "missingOutcome": "warn",
        }
    return dict(contract)


def attach_execution_contract(rule: dict[str, Any]) -> dict[str, Any]:
    check_type = str(rule.get("checkType") or rule.get("check_type") or "")
    contract = execution_contract(check_type)
    if check_type == "credential":
        providers = _credential_providers(rule)
        contract["evidenceRequirements"] = [
            requirement
            if "authoritative_registry" not in requirement.get("anyOf", [])
            else {**requirement, "providers": providers}
            for requirement in contract.get("evidenceRequirements", [])
        ]
        contract["acceptedRegistryProviders"] = providers
    if check_type == "sequencing":
        searchable = f"{rule.get('rule', '')} {rule.get('condition', '')}".casefold()
        if any(
            phrase in searchable
            for phrase in (
                "all required final inspections",
                "building and life-safety systems accepted",
                "required agency approvals",
            )
        ):
            contract["requiresAllRequiredPermitStatuses"] = True
    if check_type == "value_match" and rule.get("requiresContextStandard"):
        contract["requiresContextStandard"] = True
    return {**rule, "execution": contract}


def relevant_documents(
    document_context: list[dict[str, Any]], permit_type: str | None
) -> list[dict[str, Any]]:
    if not permit_type:
        return document_context
    direct = [
        item
        for item in document_context
        if permit_type in (item.get("permit_types") or [])
    ]
    return direct or document_context


def missing_evidence_detail(rule: dict[str, Any]) -> str:
    execution = rule.get("execution") or execution_contract(str(rule.get("checkType") or ""))
    required = ", ".join(execution.get("requiredInputs", [])) or "supporting evidence"
    return f"Could not verify automatically. Required evidence: {required}."
