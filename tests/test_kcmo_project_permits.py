import pytest
from fastapi import HTTPException

from api.models import Project, ProjectPermit
from api.services.kcmo_zoning_rules import build_kcmo_rules
from api.services.manhattan_zoning_rules import build_manhattan_rules
from api.services.project_service import (
    _build_kcmo_rule_library,
    _build_kcmo_permit_review_rules,
    _build_manhattan_rule_library,
    _sync_project_permit_recommendations,
    _validate_jurisdiction_address,
)
from shared.tools.kcmo_approvals import _rule_family_id, load_approval_catalog


def _kcmo_project(scope: dict[str, bool]) -> Project:
    return Project(
        project_id="kcmo-test-project",
        name="KCMO Retail Buildout",
        address="414 E 12th St, Kansas City, MO 64106",
        project_type="commercial_tenant_improvement",
        jurisdiction="kansas_city_mo",
        scope=scope,
        custom_rules=[],
        permits=[],
    )


def _kcmo_new_commercial_project(scope: dict[str, bool]) -> Project:
    return Project(
        project_id="kcmo-new-commercial-test-project",
        name="KCMO New Commercial",
        address="414 E 12th St, Kansas City, MO 64106",
        project_type="new_commercial_construction",
        jurisdiction="kansas_city_mo",
        scope=scope,
        custom_rules=[],
        permits=[],
    )


def test_dc15_rules_are_loaded_with_authoritative_conditions():
    rules = _build_kcmo_rule_library(area="DC-15")

    assert len(rules) >= 9
    assert any(rule["rule"] == "Maximum floor area ratio" for rule in rules)
    assert any("must not exceed 15" in rule["condition"] for rule in rules)
    assert all(rule["condition"] for rule in rules)


def test_commercial_project_excludes_residential_density_checks():
    rules = _build_kcmo_rule_library(area="B2-2", project_type="commercial")
    searchable = " ".join(
        f"{rule['rule']} {rule.get('condition', '')}" for rule in rules
    ).casefold()

    assert "single-purpose residential" not in searchable
    assert "lot area per dwelling unit" not in searchable
    assert "maximum floor area ratio" in searchable


@pytest.mark.parametrize(
    ("permit_id", "category", "minimum_count"),
    [
        ("electrical", "building", 12),
        ("plumbing", "building", 12),
        ("fire_sprinkler", "fire", 14),
        ("certificate_of_occupancy", "building", 13),
    ],
)
def test_kcmo_trade_and_occupancy_review_checks_are_populated(
    permit_id: str, category: str, minimum_count: int
):
    rules = [
        rule
        for rule in _build_kcmo_permit_review_rules()
        if permit_id in rule.get("permitTypes", [])
    ]

    assert len(rules) >= minimum_count
    assert all(rule["category"] == category for rule in rules)
    assert all(rule["condition"] and rule["source"] for rule in rules)


def test_every_kansas_city_kansas_permit_family_has_review_rules():
    from api.services.project_service import _build_kck_permit_review_rules

    kck_rules = _build_kck_permit_review_rules()
    kck_types = {
        "building_permit", "electrical", "plumbing", "mechanical", "demolition",
        "fire_protection", "certificate_of_occupancy", "land_disturbance",
        "right_of_way", "utility_service", "sign", "planning_entitlement",
    }

    assert not {
        permit_type
        for permit_type in kck_types
        if not any(permit_type in rule.get("permitTypes", []) for rule in kck_rules)
    }


def test_every_canonical_kcmo_approval_has_review_checks():
    rules = _build_kcmo_permit_review_rules()
    approvals = load_approval_catalog()["approvals"]

    missing = []
    for approval in approvals:
        if not any(
            approval["id"] in rule.get("permitTypes", [])
            for rule in rules
        ):
            missing.append(approval["id"])

    assert missing == []


@pytest.mark.parametrize(
    "classification",
    [
        "AG-R",
        "B1-1",
        "B2-2/ICO",
        "B3-2/R-0.5",
        "B4-5/HO",
        "CXO",
        "DC-1",
        "DC-15",
        "DR-3",
        "DX-10",
        "KCIA",
        "M1-5/US",
        "M4-1",
        "MPD/ICO",
        "O",
        "O-5",
        "R-0.3",
        "R-6/WHO-4",
        "R-5/R-0.5/M1-5/US",
        "R-80",
        "SC",
        "SRO/B4-2",
        "UR/HO",
    ],
)
def test_every_kcmo_zone_family_generates_automatic_rules(classification: str):
    rules = build_kcmo_rules(classification, {"ordinance": "ORD-TEST"})

    assert rules
    assert all(rule.get("condition") for rule in rules)
    assert all("ask the user to supply" not in rule["condition"].casefold() for rule in rules)


def test_split_zoning_generates_rules_for_every_base_district_and_overlay():
    rules = build_kcmo_rules("R-5/R-0.5/M1-5/US")
    groups = {rule["group"] for rule in rules}

    assert "R-5 zoning standards" in groups
    assert "R-0.5 zoning standards" in groups
    assert "M1-5 zoning standards" in groups
    assert "US zoning standards" in groups
    assert any(rule["rule"] == "Split-zoning boundaries" for rule in rules)


@pytest.mark.parametrize(
    "district",
    [
        "BC", "BP", "CA", "CC", "CD", "CN", "ICS", "IG", "IL", "LR",
        "MX", "PI-1", "PI-2", "PUD", "RC", "RH", "RL", "RL-A", "RM", "UC",
    ],
)
def test_every_manhattan_gis_district_generates_automatic_rules(district: str):
    rules = build_manhattan_rules(
        district,
        {"ordinance": "ORD-TEST", "attributes": {"PUDTYPE": "Mixed Use"}},
    )

    assert rules
    assert all(rule.get("condition") for rule in rules)
    assert all("ask the user to supply" not in rule["condition"].casefold() for rule in rules)


def test_manhattan_commercial_rules_include_numeric_district_standards():
    rules = build_manhattan_rules("BC")

    assert any(rule["rule"] == "Maximum building height" and "45 ft" in rule["condition"] for rule in rules)
    assert any(rule["rule"] == "Minimum lot area" and "7,500 sq ft" in rule["condition"] for rule in rules)
    assert any(rule["rule"] == "Minimum building setbacks" for rule in rules)


def test_manhattan_project_library_exposes_generated_conditions():
    rules = _build_manhattan_rule_library(area="CD", project_type="mixed_use")

    assert any(rule["rule"] == "Downtown building height" for rule in rules)
    assert any(rule.get("condition") for rule in rules)


def test_manhattan_split_zoning_loads_every_detected_district():
    rules = build_manhattan_rules("BC/RM")
    groups = {rule["group"] for rule in rules}

    assert "BC zoning standards" in groups
    assert "RM zoning standards" in groups
    assert any(rule["rule"] == "Split-zoning boundaries" for rule in rules)


def _seattle_project(scope: dict[str, bool]) -> Project:
    return Project(
        project_id="seattle-test-project",
        name="Seattle Retail Buildout",
        address="100 Pine St, Seattle, WA 98101",
        project_type="commercial_tenant_improvement",
        jurisdiction="seattle_wa",
        scope=scope,
        custom_rules=[],
        permits=[],
    )


def _manhattan_project(scope: dict[str, bool]) -> Project:
    return Project(
        project_id="manhattan-test-project",
        name="Manhattan Mixed Use",
        address="100 Manhattan Town Center, Manhattan, KS 66502",
        project_type="new_commercial_construction",
        jurisdiction="manhattan_ks",
        scope=scope,
        custom_rules=[],
        permits=[],
    )


def test_kcmo_scope_generates_permit_bundle():
    project = _kcmo_project(
        {
            "alteration": True,
            "electrical_work": True,
            "plumbing_work": True,
            "mechanical_hvac_work": True,
            "fire_alarm_sprinkler_work": True,
            "change_use_occupancy": True,
        }
    )

    _sync_project_permit_recommendations(project)

    permit_types = {permit.permit_type for permit in project.permits}
    assert "commercial_building" in permit_types
    assert "electrical" in permit_types
    assert "plumbing" in permit_types
    assert "mechanical" in permit_types
    assert "fire_sprinkler" in permit_types
    assert "fire_alarm" in permit_types
    assert "certificate_of_occupancy" in permit_types
    building = next(permit for permit in project.permits if permit.permit_type == "commercial_building")
    assert building.recommendation_evidence["matchResult"]["confirmedFacts"]


def test_kcmo_new_commercial_defaults_generate_permits():
    project = _kcmo_new_commercial_project({"new_construction": True})

    _sync_project_permit_recommendations(project)

    permit_types = {permit.permit_type for permit in project.permits}
    assert "commercial_building" in permit_types
    assert "certificate_of_occupancy" in permit_types
    building = next(permit for permit in project.permits if permit.permit_type == "commercial_building")
    assert building.recommendation_evidence["projectFacts"]["projectType"] == "new_commercial_construction"
    assert building.recommendation_evidence["matchResult"]["policy"] == (
        "authoritative catalog with explicit project facts"
    )


def test_seattle_ti_generates_default_and_trade_permits():
    project = _seattle_project(
        {
            "electrical_work": True,
            "plumbing_work": True,
            "mechanical_hvac_work": True,
            "fire_alarm_sprinkler_work": True,
        }
    )

    _sync_project_permit_recommendations(project)

    permit_types = {permit.permit_type for permit in project.permits}
    assert "building_construction" in permit_types
    assert "mechanical" in permit_types
    assert "plumbing" in permit_types
    assert "electrical" in permit_types
    assert "fire_alarm_suppression" in permit_types
    assert next(permit for permit in project.permits if permit.permit_type == "building_construction").required_documents


def test_manhattan_ks_scope_generates_catalog_permits():
    project = _manhattan_project(
        {
            "new_construction": True,
            "electrical_work": True,
            "plumbing_work": True,
            "mechanical_hvac_work": True,
            "signs": True,
            "grading_land_disturbance": True,
        }
    )

    _sync_project_permit_recommendations(project)

    permit_types = {permit.permit_type for permit in project.permits}
    assert "building_permit" in permit_types
    assert "electrical" in permit_types
    assert "plumbing" in permit_types
    assert "mechanical" in permit_types
    assert "sign_permit" in permit_types
    assert "floodplain_development" in permit_types
    building = next(permit for permit in project.permits if permit.permit_type == "building_permit")
    assert building.required_documents
    assert building.recommendation_evidence["projectFacts"]["jurisdiction"] == "manhattan_ks"


def test_kcmo_removed_scope_keeps_permit_visible_and_asks_for_confirmation():
    project = _kcmo_project({"plumbing_work": True})
    _sync_project_permit_recommendations(project)
    plumbing = next(permit for permit in project.permits if permit.permit_type == "plumbing")
    assert plumbing.requirement_status == "required"

    project.scope = {"plumbing_work": False}
    _sync_project_permit_recommendations(project)

    assert plumbing.requirement_status == "needs_confirmation"
    questions = plumbing.recommendation_evidence["questions"]
    assert [question["key"] for question in questions] == [
        "plumbing_work_confirmed",
        "special_plumbing_waste",
    ]
    assert plumbing.next_action == "Answer the permit-specific questions shown on this card."


def test_kcmo_catalog_keeps_canonical_and_exact_workflows_visible_without_duplicates():
    project = _kcmo_new_commercial_project({"new_construction": True, "plumbing_work": True})

    _sync_project_permit_recommendations(project)

    assert len(project.permits) > 45
    assert len({permit.permit_type for permit in project.permits}) == len(project.permits)
    assert len([permit for permit in project.permits if permit.permit_type == "plumbing"]) == 1
    exact = [permit for permit in project.permits if permit.permit_type.startswith("compass_")]
    assert exact
    assert all(permit.recommendation_evidence["questions"] for permit in exact)


def test_permit_sync_removes_legacy_duplicates_and_preserves_user_managed_record():
    project = _kcmo_new_commercial_project({"new_construction": True})
    _sync_project_permit_recommendations(project)
    system_permit = next(
        permit for permit in project.permits if permit.permit_type == "commercial_building"
    )
    manual_duplicate = ProjectPermit(
        permit_id="manual-survivor",
        project_id=project.project_id,
        permit_type=system_permit.permit_type,
        permit_name=system_permit.permit_name,
        issuing_authority=system_permit.issuing_authority,
        jurisdiction=project.jurisdiction,
        requirement_status="manual",
        lifecycle_status="not_started",
        origin="manual",
    )
    project.permits.append(manual_duplicate)

    _sync_project_permit_recommendations(project)

    matching = [
        permit for permit in project.permits if permit.permit_type == system_permit.permit_type
    ]
    assert matching == [manual_duplicate]


def test_exact_compass_question_resolves_only_that_workflow():
    project = _kcmo_new_commercial_project({"new_construction": True})
    _sync_project_permit_recommendations(project)
    conditional = next(
        permit
        for permit in project.permits
        if permit.permit_type.startswith("compass_")
        and permit.requirement_status == "needs_confirmation"
    )
    question = conditional.recommendation_evidence["questions"][0]

    project.permit_answers = {question["key"]: True}
    _sync_project_permit_recommendations(project)
    assert conditional.requirement_status == "required"

    project.permit_answers = {question["key"]: False}
    _sync_project_permit_recommendations(project)
    assert conditional.requirement_status == "not_required"


def test_ur_project_requires_development_plan_and_surfaces_fire_water_question():
    project = _kcmo_new_commercial_project(
        {"new_construction": True, "fire_alarm_sprinkler_work": True}
    )
    project.area = "UR"

    _sync_project_permit_recommendations(project)

    ur_plan = next(permit for permit in project.permits if permit.permit_type == "ur_development_plan")
    fire_service = next(permit for permit in project.permits if permit.permit_type == "fire_water_service")
    assert ur_plan.requirement_status == "required"
    assert fire_service.requirement_status == "needs_confirmation"
    assert fire_service.recommendation_evidence["questions"][0]["key"] == "new_fire_water_service"


def test_permit_answer_reclassifies_conditional_approval():
    project = _kcmo_new_commercial_project({"new_construction": True})
    project.permit_answers = {"new_fire_water_service": True}

    _sync_project_permit_recommendations(project)

    fire_service = next(permit for permit in project.permits if permit.permit_type == "fire_water_service")
    assert fire_service.requirement_status == "required"
    assert "new fire water service" in fire_service.reason.casefold()


def test_kcmo_rejects_kansas_city_kansas_address():
    with pytest.raises(HTTPException) as exc:
        _validate_jurisdiction_address("kansas_city_mo", "701 N 7th St, Kansas City, KS 66101")

    assert exc.value.status_code == 400
    assert "Kansas City, Kansas" in exc.value.detail


def test_kcmo_accepts_kansas_city_missouri_address():
    _validate_jurisdiction_address("kansas_city_mo", "414 E 12th St, Kansas City, Missouri 64106")
    _validate_jurisdiction_address("kansas_city_mo", "414 E 12th St, Kansas City, MO 64106")
