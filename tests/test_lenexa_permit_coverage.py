import json
from collections import Counter
from pathlib import Path

from api.models import Project
from api.services.lenexa_zoning_rules import DISTRICT_STANDARDS, build_lenexa_rules, has_lenexa_rule_coverage, normalize_lenexa_district
from api.services.project_service import DEFAULT_SCOPE, _build_lenexa_permit_review_rules, _sync_project_permit_recommendations
from api.services.zoning_service import JURISDICTION_ZONING, _address_looks_complete
from shared.analysis.custom_rules import _official_standard_evidence
from shared.tools.knowledge import list_jurisdictions, resolve_knowledge_root
from shared.tools.lenexa_permits import all_lenexa_applications, load_lenexa_source_registry, match_lenexa_applications, rules_for_application


ROOT = Path(__file__).resolve().parents[1] / "knowledge" / "kansas" / "lenexa"


def test_lenexa_exact_catalog_matches_coverage_contract():
    manifest = json.loads((ROOT / "coverage_manifest.json").read_text(encoding="utf-8"))
    applications = all_lenexa_applications()
    assert len(applications) == manifest["coverage_contract"]["total_exact_workflows"] == 83
    assert len({item["id"] for item in applications}) == 83
    assert Counter(item["category"] for item in applications) == {
        "Building and Trade": 25,
        "Planning and Land Use": 12,
        "Engineering and Public Works": 6,
        "Utilities and County": 4,
        "Fire Prevention": 8,
        "State and Federal": 3,
        "Business and Operational": 25,
    }


def test_every_lenexa_workflow_is_sourced_reachable_and_questioned():
    sources = {item["id"]: item for item in load_lenexa_source_registry()["sources"]}
    for application in all_lenexa_applications():
        assert application["source_id"] in sources
        assert sources[application["source_id"]]["url"].startswith("https://")
        assert application["documents"]
        assert application["scope"]
        assert set(application["scope"]) <= set(DEFAULT_SCOPE)
        substantive = rules_for_application(application)
        assert len(substantive) >= 2, application["id"]
        assert not any(rule["id"] == f"{application['id']}_applicability" for rule in substantive)
    matches = match_lenexa_applications({key: True for key in DEFAULT_SCOPE}, "mixed_use")
    assert len(matches) == 83
    assert all(item["requirement_status"] in {"required", "needs_confirmation"} for item in matches)
    assert all(item["requirement_status"] == "required" or item["questions"] for item in matches)


def test_every_lenexa_workflow_has_complete_evidence_gated_checks():
    rules = _build_lenexa_permit_review_rules()
    assert len(rules) >= 350
    for application in all_lenexa_applications():
        app_rules = [rule for rule in rules if f"lenexa_{application['id']}" in rule["permitTypes"]]
        assert app_rules
        assert len([rule for rule in app_rules if rule["checkType"] == "document_presence"]) >= len(application["documents"])
        assert {"applicability", "document_presence", "cross_document", "sequencing"} <= {rule["checkType"] for rule in app_rules}
    assert all(rule["implementation"]["status"] == "complete" for rule in rules)
    assert all(rule["execution"]["passRequiresEvidence"] is True for rule in rules)
    providers = {provider for rule in rules for provider in rule.get("execution", {}).get("acceptedRegistryProviders", [])}
    assert not {"kcmo_contractor_directory", "missouri_professional_license_search"} & providers
    assert {"kansas_professional_license_search", "johnson_county_contractor_licensing"} <= providers


def test_lenexa_project_stores_only_exact_deterministic_candidates():
    scope = {key: True for key in DEFAULT_SCOPE}
    project = Project(project_id="lenexa-test", name="Lenexa mixed use", address="17101 W 87th St Pkwy, Lenexa, KS 66219", project_type="mixed_use", jurisdiction="lenexa_ks", scope=scope, custom_rules=[], permits=[])
    _sync_project_permit_recommendations(project)
    assert len(project.permits) == 83
    assert all(permit.permit_type.startswith("lenexa_") for permit in project.permits)
    assert all(permit.recommendation_evidence["matchResult"]["usesVectorOrLlm"] is False for permit in project.permits)


def test_lenexa_zoning_is_fail_closed_for_fixed_and_planned_districts():
    fixed = build_lenexa_rules("R-1", {"attributes": {}})
    planned = build_lenexa_rules("CP-2", {"attributes": {}})
    assert has_lenexa_rule_coverage("R-1")
    assert len(fixed) >= 11
    assert all(rule["implementation"]["status"] == "complete" for rule in fixed)
    assert "Approved development plan and conditions" in {rule["rule"] for rule in planned}
    fixed_height = next(rule for rule in fixed if rule["rule"] == "R-1 maximum height")
    assert "35 feet" in fixed_height["condition"]
    assert fixed_height["requiresResolvedStandardValues"] is False
    unresolved = next(rule for rule in planned if rule["rule"] == "Approved-plan controlling values")
    assert _official_standard_evidence(unresolved, {"zoningProfile": {"district": "CP-2"}}) == []


def test_every_lenexa_gis_district_has_exact_or_plan_controlled_rules():
    gis_values = {
        "AG", "BP1", "BP2", "BPS", "CC", "CP1", "CP2", "CP3", "CP4", "CPO",
        "HBD", "NPO", "PMU", "PUD", "R1", "RE", "RP1", "RP2", "RP3", "RP4", "RP5", "RPE",
    }
    for gis_value in gis_values:
        district = normalize_lenexa_district(gis_value)
        assert has_lenexa_rule_coverage(gis_value), gis_value
        rules = build_lenexa_rules(gis_value, {"attributes": {}})
        assert rules
        assert not any(rule["rule"] == "Unmapped district standards" for rule in rules)
        if district in DISTRICT_STANDARDS:
            assert any("Under Lenexa UDC" in rule["condition"] for rule in rules)
        else:
            assert any(rule["rule"] == "Approved development plan and conditions" for rule in rules)


def test_lenexa_planned_values_cannot_pass_without_controlling_record():
    rules = build_lenexa_rules("CC", {"attributes": {"ORDINANCE": "4966", "RZ": "03-08"}})
    titles = {rule["rule"] for rule in rules}
    assert {"CC building height ranges", "Approved-plan controlling values", "Parcel-specific zoning action"} <= titles
    for title in {"Approved-plan controlling values", "Proposal matches approved plan"}:
        rule = next(item for item in rules if item["rule"] == title)
        assert rule["requiresResolvedStandardValues"] is True
        assert _official_standard_evidence(rule, {"zoningProfile": {"district": "CC"}}) == []


def test_lenexa_is_a_first_class_jurisdiction():
    ids = {item["id"] for item in list_jurisdictions()}
    assert "lenexa_ks" in ids
    assert resolve_knowledge_root("lenexa_ks") == ROOT


def test_complete_wrong_city_address_reaches_geocoder_for_precise_error():
    config = JURISDICTION_ZONING["lenexa_ks"]
    assert _address_looks_complete("411 Main St, Kansas City, MO 64105", config)
    assert not _address_looks_complete("Main St, Lenexa, KS", config)
