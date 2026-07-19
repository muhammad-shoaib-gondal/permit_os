from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from api.models import Project
from api.services.project_service import _sync_project_permit_recommendations
from shared.tools.kcmo_permits import (
    applications_for_category,
    compass_url,
    load_compass_catalog,
    load_permit_rules,
    match_kcmo_applications,
    rule_family_for_category,
)
from shared.tools.local_vector_store import LocalKnowledgeVectorStore
from shared.tools.knowledge import resolve_knowledge_root


def test_live_compass_snapshot_has_every_captured_application():
    catalog = load_compass_catalog()
    manifest = json.loads(
        (resolve_knowledge_root("kansas_city_mo") / "coverage_manifest.json").read_text(encoding="utf-8")
    )

    assert len(catalog["permit_applications"]) == 108
    assert len(catalog["plan_applications"]) == 88
    assert len({item["id"] for item in catalog["permit_applications"]}) == 108
    assert len({item["id"] for item in catalog["plan_applications"]}) == 88
    assert Counter(item["category"] for item in catalog["permit_applications"]) == Counter(
        manifest["catalog"]["permit_categories"]
    )


def test_every_permit_category_has_a_cited_rule_family():
    catalog = load_compass_catalog()
    for application in catalog["permit_applications"]:
        family = rule_family_for_category(application["category"])
        assert family, application
        assert family["rules"], application
        assert family["sources"], application


def test_manifest_files_and_rule_source_ids_are_complete():
    root = resolve_knowledge_root("kansas_city_mo")
    manifest = json.loads((root / "coverage_manifest.json").read_text(encoding="utf-8"))
    registry = json.loads((root / "source_registry.json").read_text(encoding="utf-8"))
    rules = load_permit_rules()
    source_ids = {source["id"] for source in registry["sources"]}

    assert all((root / filename).is_file() for filename in manifest["required_files"])
    referenced = {
        source_id
        for rule in rules["global_rules"] + rules["category_rules"]
        for source_id in rule["sources"]
    }
    assert referenced <= source_ids


def test_every_application_gets_a_deterministic_portal_url():
    catalog = load_compass_catalog()
    for kind, key in (("permit", "permit_applications"), ("plan", "plan_applications")):
        for application in catalog[key]:
            assert compass_url(kind, application["id"]).endswith(
                f"#/{kind}/apply/{application['id']}/0/0"
            )


def test_selecting_electrical_returns_all_eight_exact_permit_routes():
    electrical = applications_for_category("electrical")
    assert len(electrical) == 8
    assert {item["id"] for item in electrical} == {576, 767, 583, 434, 430, 431, 772, 432}

    matched = match_kcmo_applications(
        {"electrical_work": True}, "commercial_tenant_improvement"
    )
    permits = [item for item in matched if item["application_kind"] == "permit"]
    assert {item["id"] for item in permits} == {576, 767, 583, 434, 430, 431, 772, 432}
    assert next(item for item in permits if item["id"] == 576)["requirement_status"] == "required"
    assert all(item["requirement_status"] in {"required", "needs_confirmation", "not_required"} for item in permits)
    active_ids = {item["id"] for item in permits if item["requirement_status"] != "not_required"}
    assert active_ids == {576, 430}


def test_residential_solar_returns_electrical_catalog_and_solar_plan():
    matched = match_kcmo_applications(
        {"electrical_work": True, "solar_battery_generator_ev": True},
        "single_family",
        {"solar": True, "service_amps": 400},
    )
    permit_ids = {item["id"] for item in matched if item["application_kind"] == "permit"}
    plan_ids = {item["id"] for item in matched if item["application_kind"] == "plan"}

    assert permit_ids == {576, 767, 583, 434, 430, 431, 772, 432}
    assert 923 in plan_ids
    assert next(item for item in matched if item["id"] == 583)["requirement_status"] == "required"


def test_electrical_rule_pack_contains_every_critical_branch():
    rules = load_permit_rules()
    electrical = next(item for item in rules["category_rules"] if item["id"] == "electrical")
    searchable = " ".join(electrical["rules"] + electrical["exemptions"]).casefold()

    for phrase in (
        "400 amps",
        "800 through 1199 amps",
        "1200 amps",
        "600 volts",
        "transformers",
        "generators",
        "battery systems",
        "fire pumps",
        "wind turbines",
        "automatic transfer switches",
        "solar",
        "limited service",
        "reconnect",
        "fire alarm",
        "security alarm",
        "floodplain",
    ):
        assert phrase in searchable
    assert set(rules["electrical_application_rules"]) == {
        "576", "767", "583", "434", "430", "431", "772", "432"
    }


def test_estatepermit_project_stores_all_exact_electrical_candidates():
    project = Project(
        project_id="kcmo-complete-electrical",
        name="Electrical Scope",
        address="414 E 12th St, Kansas City, MO 64106",
        project_type="commercial_tenant_improvement",
        jurisdiction="kansas_city_mo",
        scope={"electrical_work": True},
        custom_rules=[],
        permits=[],
    )

    _sync_project_permit_recommendations(project)

    exact = {permit.permit_type for permit in project.permits if permit.permit_type.startswith("compass_permit_")}
    assert exact == {
        "compass_permit_576",
        "compass_permit_767",
        "compass_permit_583",
        "compass_permit_434",
        "compass_permit_430",
        "compass_permit_431",
        "compass_permit_772",
        "compass_permit_432",
    }


def test_commercial_cafe_hides_known_residential_compass_routes():
    scope = {
        "new_construction": True,
        "alteration": True,
        "structural_work": True,
        "electrical_work": True,
        "plumbing_work": True,
        "fire_alarm_sprinkler_work": True,
    }
    matched = match_kcmo_applications(scope, "commercial")
    active = [item for item in matched if item["requirement_status"] != "not_required"]
    searchable = " ".join(item["name"] for item in active).casefold()

    assert "residential" not in searchable
    assert "single family" not in searchable
    assert "duplex" not in searchable
    assert "townhouse" not in searchable
    assert {item["id"] for item in active} == {
        567, 587, 618, 430, 576, 772, 435, 592, 442, 608, 652
    }


def test_local_vector_index_searches_rules_without_deciding_applicability(tmp_path: Path):
    index_path = tmp_path / "kcmo.sqlite3"
    store = LocalKnowledgeVectorStore(index_path)
    count = store.rebuild(resolve_knowledge_root("kansas_city_mo"))
    results = store.search("1200 amp electrical service generator battery IB160", limit=10)

    assert count >= 200
    assert store.metadata()["authority_policy"] == "retrieval-only"
    assert any("electrical" in (result.title + " " + result.text).casefold() for result in results)
    assert any("ib160" in (result.title + " " + result.text).casefold() for result in results)
