import json
from collections import Counter
from pathlib import Path

from api.models import Project
from api.services.overland_park_zoning_rules import GIS_DISTRICTS, build_overland_park_rules, has_overland_park_rule_coverage
from api.services.project_service import DEFAULT_SCOPE, _build_overland_park_permit_review_rules, _sync_project_permit_recommendations
from api.services.zoning_service import JURISDICTION_ZONING, _address_looks_complete
from shared.tools.knowledge import list_jurisdictions, resolve_knowledge_root
from shared.tools.overland_park_permits import all_overland_park_applications, load_overland_park_source_registry, match_overland_park_applications, rules_for_application

ROOT = Path(__file__).resolve().parents[1] / "knowledge" / "kansas" / "overland_park"


def test_overland_park_exact_catalog_matches_manifest():
    manifest = json.loads((ROOT / "coverage_manifest.json").read_text(encoding="utf-8"))
    applications = all_overland_park_applications()
    assert len(applications) == manifest["coverage_contract"]["total_exact_workflows"] == 85
    assert len({item["id"] for item in applications}) == 85
    assert sum(Counter(item["category"] for item in applications).values()) == 85


def test_every_workflow_is_sourced_reachable_and_questioned():
    sources = {item["id"]: item for item in load_overland_park_source_registry()["sources"]}
    for application in all_overland_park_applications():
        assert application["source_id"] in sources
        assert sources[application["source_id"]]["url"].startswith("https://")
        assert application["documents"]
        assert application["scope"]
        assert set(application["scope"]) <= set(DEFAULT_SCOPE)
        assert len(rules_for_application(application)) >= 2, application["id"]
    matches = match_overland_park_applications({key: True for key in DEFAULT_SCOPE}, "mixed_use")
    assert len(matches) == 85
    assert all(item["requirement_status"] in {"required", "needs_confirmation"} for item in matches)
    assert all(item["requirement_status"] == "required" or item["questions"] for item in matches)


def test_every_workflow_has_evidence_gated_checks():
    rules = _build_overland_park_permit_review_rules()
    for application in all_overland_park_applications():
        app_rules = [rule for rule in rules if f"overland_park_{application['id']}" in rule["permitTypes"]]
        assert len(app_rules) >= 10, application["id"]
        assert len([rule for rule in app_rules if rule["checkType"] == "document_presence"]) >= len(application["documents"])
        assert {"applicability", "document_presence", "cross_document", "sequencing"} <= {rule["checkType"] for rule in app_rules}
    assert all(rule["implementation"]["status"] == "complete" for rule in rules)
    assert all(rule["execution"]["passRequiresEvidence"] is True for rule in rules)
    assert all(rule["execution"]["missingOutcome"] == "warn" for rule in rules)


def test_project_stores_only_exact_deterministic_candidates():
    scope = {key: True for key in DEFAULT_SCOPE}
    project = Project(project_id="op-test", name="Overland Park mixed use", address="8500 Santa Fe Dr, Overland Park, KS 66212", project_type="mixed_use", jurisdiction="overland_park_ks", scope=scope, custom_rules=[], permits=[])
    _sync_project_permit_recommendations(project)
    assert len(project.permits) == 85
    assert all(permit.permit_type.startswith("overland_park_") for permit in project.permits)
    assert all(permit.recommendation_evidence["matchResult"]["usesVectorOrLlm"] is False for permit in project.permits)


def test_every_official_gis_district_is_fail_closed_and_covered():
    assert len(GIS_DISTRICTS) == 58
    for district in GIS_DISTRICTS:
        assert has_overland_park_rule_coverage(district)
        rules = build_overland_park_rules(district, {"attributes": {}})
        assert len(rules) >= 11, district
        assert all(rule["implementation"]["status"] == "complete" for rule in rules)
        assert all(rule["execution"]["missingOutcome"] == "warn" for rule in rules)


def test_overland_park_is_first_class_jurisdiction():
    assert "overland_park_ks" in {item["id"] for item in list_jurisdictions()}
    assert resolve_knowledge_root("overland_park_ks") == ROOT
    config = JURISDICTION_ZONING["overland_park_ks"]
    assert _address_looks_complete("8500 Santa Fe Dr, Overland Park, KS 66212", config)
    assert not _address_looks_complete("Santa Fe Dr, Overland Park, KS", config)
