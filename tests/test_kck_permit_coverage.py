import json
from collections import Counter
from pathlib import Path

import pytest
from fastapi import HTTPException

from api.models import Project
from api.services.project_service import _sync_project_permit_recommendations, _validate_jurisdiction_address
from shared.tools.kck_permits import all_kck_applications, match_kck_applications, rules_for_application
from shared.tools.knowledge import list_jurisdictions, resolve_knowledge_root
from shared.tools.local_vector_store import LocalKnowledgeVectorStore, build_kck_vector_index


ROOT = Path(__file__).resolve().parents[1] / "knowledge" / "kansas" / "kansas_city"


def test_kck_coverage_contract_matches_exact_catalog():
    manifest = json.loads((ROOT / "coverage_manifest.json").read_text(encoding="utf-8"))
    applications = all_kck_applications()
    counts = Counter(item["category"] for item in applications)

    assert len(applications) == manifest["coverage_contract"]["total_exact_workflows"] == 73
    assert counts == {
        "Building and Trade": 19,
        "Planning and Land Use": 31,
        "Public Works and Utilities": 17,
        "Fire Prevention": 6,
    }
    assert len({item["id"] for item in applications}) == len(applications)


def test_every_kck_application_has_an_official_registered_source():
    registry = json.loads((ROOT / "source_registry.json").read_text(encoding="utf-8"))
    sources = {item["id"]: item for item in registry["sources"]}

    for application in all_kck_applications():
        assert application["source_id"] in sources
        assert sources[application["source_id"]]["url"].startswith("https://")
        assert application["documents"]
        assert application["scope"]
        assert rules_for_application(application)


def test_electrical_scope_keeps_every_kck_electrical_workflow_visible():
    matches = match_kck_applications({"electrical_work": True})
    ids = {item["id"] for item in matches}

    assert {"electrical", "temporary_electrical", "bpu_electric_service", "bpu_temporary_service"} <= ids
    assert next(item for item in matches if item["id"] == "electrical")["requirement_status"] == "required"
    assert all(item["rule_ids"] for item in matches)


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
    exact = next(permit for permit in project.permits if permit.permit_type == "kck_electrical")
    assert exact.recommendation_evidence["matchResult"]["usesVectorOrLlm"] is False


def test_kck_commercial_project_marks_residential_routes_not_required():
    matches = match_kck_applications(
        {"new_construction": True, "change_use_occupancy": True},
        "commercial",
    )
    by_id = {item["id"]: item for item in matches}

    assert by_id["residential_building"]["requirement_status"] == "not_required"
    assert by_id["short_term_rental_admin"]["requirement_status"] == "not_required"
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
