"""KCMO MVP: permit router, pack validation, checklist matching, package builder."""

from __future__ import annotations

from shared.schemas.kcmo_intake import FloodplainStatus, KcmoIntake, ProjectCategory, ScopeType
from shared.schemas.project_brief import ProjectBrief, ProjectType
from shared.tools.kcmo.kcmo_package_builder import build_kcmo_package
from shared.tools.kcmo.kcmo_permit_router import route_kcmo_permits
from shared.tools.kcmo.validate_pack import validate_kcmo_knowledge_pack
from shared.tools.kcmo.checklist_match import match_filename_to_checklist_keys


def test_kcmo_pack_validates():
    result = validate_kcmo_knowledge_pack()
    assert result["ok"] is True, result["errors"]
    assert result["coverage_status"] == "active"


def test_single_family_addition_routes_trades():
    intake = KcmoIntake(
        project_category=ProjectCategory.SINGLE_FAMILY,
        scope_type=ScopeType.ADDITION,
        includes_electrical=True,
        includes_mechanical=True,
        owner_occupied=True,
        floodplain_status=FloodplainStatus.NO,
    )
    permits = route_kcmo_permits(intake)
    ids = {p["permit_type"] for p in permits}
    assert "residential_building" in ids
    assert "electrical" in ids
    assert "mechanical" in ids
    assert "homeowner_affidavit_note" in ids


def test_multifamily_new_sprinkler_unknown():
    intake = KcmoIntake(
        project_category=ProjectCategory.MULTIFAMILY,
        scope_type=ScopeType.NEW_CONSTRUCTION,
        dwelling_units=12,
        sprinklered="unknown",
        multiple_buildings=True,
    )
    permits = route_kcmo_permits(intake)
    ids = {p["permit_type"] for p in permits}
    assert "multifamily_building_review" in ids
    assert "certificate_of_occupancy" in ids
    assert "fire_sprinkler" in ids
    assert "multiple_building_data_sheet" in ids
    fire = next(p for p in permits if p["permit_type"] == "fire_sprinkler")
    assert fire["requirement_status"] == "likely_required"


def test_commercial_tenant_finish_change_of_use():
    intake = KcmoIntake(
        project_category=ProjectCategory.COMMERCIAL,
        scope_type=ScopeType.TENANT_FINISH,
        tenant_finish=True,
        existing_use="Retail",
        proposed_use="Restaurant",
        includes_electrical=True,
        includes_plumbing=True,
        includes_mechanical=True,
        public_access=True,
    )
    permits = route_kcmo_permits(intake)
    ids = {p["permit_type"] for p in permits}
    assert "commercial_building" in ids
    assert "tenant_finish" in ids
    assert "change_of_occupancy" in ids
    assert "certificate_of_occupancy" in ids
    assert "electrical" in ids


def test_floodplain_data_gap_in_package():
    intake = KcmoIntake(
        project_category=ProjectCategory.SINGLE_FAMILY,
        scope_type=ScopeType.ALTERATION,
        floodplain_status=FloodplainStatus.UNKNOWN,
    )
    brief = ProjectBrief(
        project_name="Flood Gap Home",
        address="100 Main St, Kansas City, MO 64106",
        jurisdiction="kansas_city_mo",
        project_type=ProjectType.SINGLE_FAMILY,
        kcmo_intake=intake.model_dump(mode="json"),
    )
    package = build_kcmo_package(brief, intake, zoning_profile={"district": "R-5"})
    assert any("floodplain" in g.lower() or "Floodplain" in g for g in package["data_gaps"])
    assert package["fee_estimate"]["estimate_status"] == "data_gap"


def test_checklist_filename_matching():
    keys = match_filename_to_checklist_keys("Architectural_Floor_Plans_A100.pdf")
    assert "architectural_plans" in keys
    keys2 = match_filename_to_checklist_keys("Site Plan - Civil.pdf")
    assert "site_plan" in keys2
