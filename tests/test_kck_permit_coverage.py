import json
from collections import Counter
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.models import Project
from api.services.kck_zoning_rules import build_kck_rules, has_kck_rule_coverage
from api.services.project_service import (
    _build_kck_permit_review_rules,
    _sync_project_permit_recommendations,
    _validate_jurisdiction_address,
)
from shared.analysis.custom_rules import _official_standard_evidence
from shared.tools.kck_permits import (
    all_kck_applications,
    load_kck_source_registry,
    match_kck_applications,
    rules_for_application,
)
from shared.tools.knowledge import list_jurisdictions, resolve_knowledge_root
from shared.tools.local_vector_store import LocalKnowledgeVectorStore, build_kck_vector_index


ROOT = Path(__file__).resolve().parents[1] / "knowledge" / "kansas" / "kansas_city"


def test_kck_coverage_contract_matches_exact_catalog():
    manifest = json.loads((ROOT / "coverage_manifest.json").read_text(encoding="utf-8"))
    applications = all_kck_applications()
    counts = Counter(item["category"] for item in applications)

    assert len(applications) == manifest["coverage_contract"]["total_exact_workflows"] == 91
    assert counts == {
        "Building and Trade": 20,
        "Planning and Land Use": 31,
        "Public Works and Utilities": 17,
        "Fire Prevention": 11,
        "Health and Environmental": 5,
        "State and Federal": 7,
    }
    assert len({item["id"] for item in applications}) == len(applications)


def test_every_kck_application_has_an_official_registered_source():
    registry = load_kck_source_registry()
    sources = {item["id"]: item for item in registry["sources"]}

    for application in all_kck_applications():
        assert application["source_id"] in sources
        assert sources[application["source_id"]]["url"].startswith("https://")
        assert application["documents"]
        assert application["scope"]
        substantive = rules_for_application(application)
        assert len(substantive) >= 2, application["id"]
        assert not any(rule["id"] == f"{application['id']}_applicability" for rule in substantive)


def test_every_kck_workflow_has_complete_executable_review_checks():
    rules = _build_kck_permit_review_rules()
    by_permit = {
        application["id"]: [
            rule
            for rule in rules
            if f"kck_{application['id']}" in rule.get("permitTypes", [])
        ]
        for application in all_kck_applications()
    }

    assert len(rules) >= 800
    assert all(by_permit.values())
    assert all(
        rule["implementation"]["status"] == "complete"
        and rule["execution"]["passRequiresEvidence"] is True
        and rule["execution"]["missingOutcome"] == "warn"
        and rule["sourceLinks"]
        for rule in rules
    )
    value_rules = [rule for rule in rules if rule.get("checkType") == "value_match"]
    assert value_rules
    contextual_value_rules = [
        rule for rule in value_rules if rule.get("requiresContextStandard")
    ]
    fixed_value_rules = [
        rule for rule in value_rules if not rule.get("requiresContextStandard")
    ]
    assert contextual_value_rules
    assert all(_official_standard_evidence(rule, {}) == [] for rule in contextual_value_rules)
    assert all(_official_standard_evidence(rule, {}) for rule in fixed_value_rules)
    for application in all_kck_applications():
        document_checks = [
            rule
            for rule in by_permit[application["id"]]
            if rule.get("checkType") == "document_presence"
        ]
        assert len(document_checks) >= len(application["documents"])

    credential_providers = {
        provider
        for rule in rules
        for provider in rule.get("execution", {}).get("acceptedRegistryProviders", [])
    }
    assert not {
        "kcmo_contractor_directory",
        "missouri_professional_license_search",
        "missouri_elevator_registry",
        "missouri_asbestos_registry",
    } & credential_providers


@pytest.mark.parametrize(
    "district",
    [
        "AG", "B-P", "C-0", "C-1", "C-2", "C-3", "C-D", "CP-1", "M-2",
        "MP-2", "R-1", "R-2", "R-3", "RP-1", "RP-4", "TND", "R-1 (Wyco)",
    ],
)
def test_every_observed_kck_zoning_family_is_fail_closed_and_covered(district):
    rules = build_kck_rules(district, {"attributes": {}})

    assert has_kck_rule_coverage(district)
    assert len(rules) >= 5
    assert all(rule["implementation"]["status"] == "complete" for rule in rules)
    assert all(rule["execution"]["passRequiresEvidence"] is True for rule in rules)
    assert all(rule["execution"]["missingOutcome"] == "warn" for rule in rules)


def test_kck_planned_legacy_historic_and_split_zoning_get_controlling_record_checks():
    planned = build_kck_rules("RP-2", {"attributes": {}})
    legacy = build_kck_rules("R-1 (Wyco)", {"attributes": {}})
    flagged = build_kck_rules(
        "C-2/R-1",
        {"attributes": {"SPLIT_ZONE": "Y", "HISTORIC": "Y", "ENVIRONS": "Y"}},
    )

    assert {"Approved preliminary development plan", "Approved final development plan"} <= {
        rule["rule"] for rule in planned
    }
    assert "Legacy Wyandotte County district control" in {rule["rule"] for rule in legacy}
    assert {
        "Split-zoning boundary",
        "Historic property approval",
        "Historic environs review",
    } <= {rule["rule"] for rule in flagged}


def test_unresolved_kck_numeric_standards_cannot_be_treated_as_official_evidence():
    generic = next(
        rule
        for rule in build_kck_rules("UNKNOWN", {"attributes": {}})
        if rule["rule"] == "Maximum building height"
    )
    exact = next(
        rule
        for rule in build_kck_rules("C-2", {"attributes": {}})
        if rule["rule"] == "C-2 maximum height"
    )
    context = {"zoningProfile": {"district": "UNKNOWN"}}

    assert _official_standard_evidence(generic, context) == []
    assert _official_standard_evidence(exact, context)


@pytest.mark.parametrize(
    "district",
    [
        "AG", "R", "R-1", "RP-1", "R-1(B)", "RP-1(B)", "R-2", "RP-2",
        "R-2(B)", "RP-2(B)", "R-3", "RP-3", "R-4", "RP-4", "R-5", "RP-5",
        "R-6", "RP-6", "R-M", "RP-M", "C-0", "CP-0", "C-1", "CP-1", "C-D",
        "CP-D", "C-2", "CP-2", "C-3", "CP-3", "M-1", "MP-1", "M-2", "MP-2",
        "M-3", "MP-3", "B-P", "AG (Wyco)", "R (Wyco)", "R-1 (Wyco)",
        "R-1A (Wyco)", "RP-1A (Wyco)", "R-1B (Wyco)", "R-2 (Wyco)",
        "R-5 (Wyco)", "RP-5 (Wyco)", "C-1 (Wyco)", "CP-2 (Wyco)",
        "CP-3 (Wyco)", "C-2 (Wyco)",
    ],
)
def test_every_fixed_gis_district_has_stored_official_standards(district):
    rules = build_kck_rules(district, {"attributes": {}})
    catalog_rules = [rule for rule in rules if "catalog-" in rule["id"]]

    assert catalog_rules
    assert all(rule["requiresResolvedStandardValues"] is False for rule in catalog_rules)
    assert all(_official_standard_evidence(rule, {}) for rule in catalog_rules)


def test_plan_controlled_gis_districts_require_the_controlling_plan():
    for district in ["RP-1", "CP-2", "MP-3", "B-P", "TND", "RP-1A (Wyco)"]:
        titles = {rule["rule"] for rule in build_kck_rules(district, {"attributes": {}})}
        assert "Approved preliminary development plan" in titles
        assert "Approved final development plan" in titles


def test_electrical_scope_keeps_every_kck_electrical_workflow_visible():
    matches = match_kck_applications({"electrical_work": True})
    ids = {item["id"] for item in matches}

    assert {"electrical", "temporary_electrical", "bpu_electric_service", "bpu_temporary_service"} <= ids
    assert next(item for item in matches if item["id"] == "electrical")["requirement_status"] == "required"
    assert all(item["rule_ids"] for item in matches)


def test_broad_sign_and_fire_scopes_do_not_require_mutually_exclusive_workflows():
    matches = {
        item["id"]: item
        for item in match_kck_applications(
            {"signs": True, "fire_alarm_sprinkler_work": True},
            "commercial",
        )
    }
    sign_ids = {
        "sign_incidental", "sign_flag", "sign_attached", "sign_detached",
        "billboard_under_300", "billboard_300_or_more",
    }
    assert all(matches[item_id]["requirement_status"] == "needs_confirmation" for item_id in sign_ids)
    assert matches["fire_alarm"]["requirement_status"] == "needs_confirmation"
    assert matches["fire_sprinkler"]["requirement_status"] == "needs_confirmation"
    assert all(matches[item_id]["questions"] for item_id in [*sign_ids, "fire_alarm", "fire_sprinkler"])


def test_kck_project_receives_exact_deterministic_candidates():
    scope = {"electrical_work": True, "plumbing_work": True, "fire_alarm_sprinkler_work": True}
    project = Project(
        project_id="kck-test",
        name="KCK renovation",
        address="701 N 7th St, Kansas City, KS 66101",
        project_type="commercial_tenant_improvement",
        jurisdiction="kansas_city_ks",
        scope=scope,
        custom_rules=[],
        permits=[],
    )

    _sync_project_permit_recommendations(project)

    exact_ids = {
        f"kck_{item['id']}"
        for item in match_kck_applications(scope, "commercial_tenant_improvement")
    }
    stored_ids = {permit.permit_type for permit in project.permits}
    assert exact_ids <= stored_ids
    assert stored_ids == exact_ids
    assert not ({"electrical", "plumbing", "fire_protection"} & stored_ids)
    exact = next(permit for permit in project.permits if permit.permit_type == "kck_electrical")
    assert exact.recommendation_evidence["matchResult"]["usesVectorOrLlm"] is False


def test_kck_conditional_state_approvals_are_visible_and_answers_reclassify_them():
    scope = {"new_construction": True, "grading_land_disturbance": True}
    initial = {item["id"]: item for item in match_kck_applications(scope, "commercial")}

    assert initial["kdhe_construction_stormwater"]["requirement_status"] == "needs_confirmation"
    assert initial["usace_section_404"]["requirement_status"] == "needs_confirmation"
    assert initial["kdhe_construction_stormwater"]["questions"]

    confirmed = {
        item["id"]: item
        for item in match_kck_applications(
            scope,
            "commercial",
            {"disturbance_one_acre": True, "waters_or_wetlands_impact": False},
        )
    }
    assert confirmed["kdhe_construction_stormwater"]["requirement_status"] == "required"
    assert confirmed["usace_section_404"]["requirement_status"] == "not_required"


def test_kck_commercial_project_marks_residential_routes_not_required():
    matches = match_kck_applications(
        {"new_construction": True, "change_use_occupancy": True},
        "commercial",
    )
    by_id = {item["id"]: item for item in matches}

    assert by_id["residential_building"]["requirement_status"] == "not_required"
    assert by_id["short_term_rental_admin"]["requirement_status"] == "not_required"
    assert by_id["commercial_building_drc"]["requirement_status"] == "needs_confirmation"


def test_kck_mixed_or_unclear_project_type_does_not_assume_a_building_route():
    for project_type in ["mixed_use", ""]:
        matches = match_kck_applications(
            {"new_construction": True, "change_use_occupancy": True},
            project_type,
        )
        by_id = {item["id"]: item for item in matches}
        assert by_id["residential_building"]["requirement_status"] == "needs_confirmation"
        assert by_id["commercial_building_drc"]["requirement_status"] == "needs_confirmation"


def test_kansas_city_jurisdictions_are_separate_menu_options():
    ids = {item["id"] for item in list_jurisdictions()}
    assert {"kansas_city_mo", "kansas_city_ks"} <= ids
    assert resolve_knowledge_root("kansas_city_ks") == ROOT


def test_kck_rejects_missouri_address_and_accepts_kansas_address():
    with pytest.raises(HTTPException) as exc:
        _validate_jurisdiction_address("kansas_city_ks", "414 E 12th St, Kansas City, Missouri 64106")
    assert exc.value.status_code == 400
    assert "Kansas City, Missouri" in exc.value.detail

    _validate_jurisdiction_address("kansas_city_ks", "701 N 7th St, Kansas City, Kansas 66101")


def test_kck_local_vector_index_is_retrieval_only(tmp_path):
    index = tmp_path / "kck.sqlite3"
    count = build_kck_vector_index(index)
    store = LocalKnowledgeVectorStore(index)

    assert count > 100
    assert store.metadata()["authority_policy"] == "retrieval-only"
    assert store.search("electrical permit licensed contractor", limit=3)
