from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from api.models import Project
from api.services.project_service import _sync_project_permit_recommendations, _usable_custom_rules
from api.services.kcmo_zoning_rules import (
    D_STANDARDS,
    M_STANDARDS,
    OB_STANDARDS,
    OVERLAY_COMPONENTS,
    R_STANDARDS,
    build_kcmo_rules,
)
from shared.tools.kcmo_approvals import load_approval_catalog
from shared.tools.kcmo_permits import (
    applications_for_category,
    compass_url,
    load_compass_catalog,
    load_permit_rules,
    match_kcmo_applications,
    rule_family_for_category,
)
from shared.tools.kcmo_review_rules import expanded_review_rules, load_review_rule_catalog
from shared.analysis.rule_coverage import catalog_implementation_report
from shared.analysis.custom_rules import _official_standard_evidence
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


def test_every_compass_category_has_a_cited_rule_family():
    catalog = load_compass_catalog()
    for key in ("permit_applications", "plan_applications"):
        for application in catalog[key]:
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


def test_every_exact_compass_workflow_has_executable_review_rules():
    rules = expanded_review_rules()
    targets = {target for rule in rules for target in rule["permitTypes"]}
    catalog = load_compass_catalog()
    expected = {
        f"compass_{kind}_{application['id']}"
        for kind, key in (("permit", "permit_applications"), ("plan", "plan_applications"))
        for application in catalog[key]
    }
    assert expected <= targets
    for target in expected:
        target_rules = [rule for rule in rules if target in rule["permitTypes"]]
        assert len(target_rules) >= 10, target
        assert {"applicability", "document_presence"} <= {rule["checkType"] for rule in target_rules}
        assert all(rule["execution"]["passRequiresEvidence"] is True for rule in target_rules)


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


def test_estatepermit_project_keeps_canonical_and_exact_electrical_candidates():
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

    electrical = [permit for permit in project.permits if permit.permit_type == "electrical"]
    exact = [permit for permit in project.permits if permit.permit_type.startswith("compass_permit_")]
    assert len(electrical) == 1
    assert {permit.permit_type for permit in exact} == {
        f"compass_permit_{application_id}"
        for application_id in {576, 767, 583, 434, 430, 431, 772, 432}
    }
    assert electrical[0].recommendation_evidence["catalogRule"]["compassApplicationIds"] == [576]


def test_complete_approval_catalog_has_45_source_backed_entries():
    catalog = json.loads(
        (resolve_knowledge_root("kansas_city_mo") / "approval_catalog.json").read_text(encoding="utf-8")
    )
    registry = json.loads(
        (resolve_knowledge_root("kansas_city_mo") / "source_registry.json").read_text(encoding="utf-8")
    )
    source_ids = {source["id"] for source in registry["sources"]}

    assert len(catalog["approvals"]) == 45
    assert {item["sequence"] for item in catalog["approvals"]} == set(range(1, 46))
    assert len({item["id"] for item in catalog["approvals"]}) == 45
    assert all(item["source_ids"] for item in catalog["approvals"])
    assert {
        source_id
        for item in catalog["approvals"]
        for source_id in item["source_ids"]
    } <= source_ids


def test_all_45_approvals_have_exact_cited_review_rule_coverage():
    root = resolve_knowledge_root("kansas_city_mo")
    approvals = json.loads((root / "approval_catalog.json").read_text(encoding="utf-8"))
    registry = json.loads((root / "source_registry.json").read_text(encoding="utf-8"))
    catalog = load_review_rule_catalog()
    source_ids = {source["id"] for source in registry["sources"]}
    approval_ids = {approval["id"] for approval in approvals["approvals"]}
    permit_ids = {permit["permit_id"] for permit in catalog["permits"]}

    assert len(catalog["permits"]) == 45
    assert permit_ids == approval_ids
    assert catalog["verified_at"] == "2026-07-21"

    for permit in catalog["permits"]:
        expanded = [
            *(
                rule
                for set_id in permit.get("include_sets", [])
                for rule in catalog["shared_rule_sets"][set_id]
            ),
            *permit["rules"],
        ]
        assert len(expanded) >= 6, permit["permit_id"]
        assert len({rule["id"] for rule in expanded}) == len(expanded), permit["permit_id"]
        for rule in expanded:
            assert rule["title"].strip(), (permit["permit_id"], rule)
            assert rule["requirement"].strip(), (permit["permit_id"], rule)
            assert rule["check_type"] in {
                "applicability",
                "document_presence",
                "value_match",
                "cross_document",
                "credential",
                "sequencing",
            }
            assert rule["severity"] in {"blocker", "warning", "info"}
            assert rule["citation"].strip()
            assert rule["source_ids"]
            assert set(rule["source_ids"]) <= source_ids
            if "question" in rule:
                assert rule["question"]["key"].strip()
                assert rule["question"]["label"].strip()
                assert rule["question"]["type"] in {"boolean", "text", "number"}


def test_expanded_review_rules_have_resolved_official_links_and_no_generic_titles():
    rules = expanded_review_rules()
    approval_ids = {
        approval["id"]
        for approval in load_approval_catalog()["approvals"]
    }

    exact_ids = {
        f"compass_{kind}_{application['id']}"
        for kind, key in (("permit", "permit_applications"), ("plan", "plan_applications"))
        for application in load_compass_catalog()[key]
    }
    assert {rule["permitTypes"][0] for rule in rules} == approval_ids | exact_ids
    assert all(rule["sourceLinks"] for rule in rules)
    assert all(
        source["url"].startswith("https://")
        for rule in rules
        for source in rule["sourceLinks"]
    )
    assert not any(re.search(r"\brequirement \d+\b", rule["rule"], re.IGNORECASE) for rule in rules)

    zoning = [rule for rule in rules if rule["permitTypes"] == ["zoning_verification"]]
    assert len(zoning) >= 18
    assert {"Official base zoning district", "Building height compliance", "Bicycle parking calculation"} <= {
        rule["rule"] for rule in zoning
    }


def test_all_review_rules_have_an_executable_evidence_contract():
    rules = expanded_review_rules()

    assert len(rules) >= 4200
    assert all(rule["execution"]["evaluator"] != "unsupported" for rule in rules)
    assert all(rule["execution"]["requiredInputs"] for rule in rules)
    assert all(rule["execution"]["passRequiresEvidence"] is True for rule in rules)


def test_far_and_other_controlling_zoning_values_require_resolved_standards():
    far = next(
        rule
        for rule in expanded_review_rules()
        if rule["id"] == "kcmo-review-zoning_verification-zv-far"
    )

    assert far["requiresContextStandard"] is True
    assert far["requiresResolvedStandardValues"] is True
    assert _official_standard_evidence(
        far,
        {"zoningProfile": {"classification": "UR"}},
    ) == []


def test_all_review_rules_have_complete_implementation_paths():
    report = catalog_implementation_report(expanded_review_rules())

    assert report["total"] >= 4200
    assert report["complete"] == report["total"]
    assert report["incomplete"] == 0
    assert all(entry["unavailableEvidenceOutcome"] == "not_verified" for entry in report["entries"])


def test_every_generated_kcmo_zoning_rule_has_a_complete_implementation_path():
    classifications = {
        *R_STANDARDS,
        *(f"{prefix}-{intensity}" for prefix in ("O", "B1", "B2", "B3", "B4") for intensity in OB_STANDARDS),
        *(f"{prefix}-{intensity}" for prefix in ("DC", "DR", "DX") for intensity in D_STANDARDS),
        *(f"{prefix}-{intensity}" for prefix in ("M1", "M2", "M3", "M4") for intensity in M_STANDARDS),
        "AG-R",
        "KCIA",
        "UR",
        "MPD",
        "SC",
        "CXO",
        "O",
        *OVERLAY_COMPONENTS,
        "WHO-1",
        "UR/HO",
        "UNKNOWN-DISTRICT",
    }
    rules = [rule for classification in classifications for rule in build_kcmo_rules(classification)]

    assert rules
    assert all(rule["implementation"]["status"] == "complete" for rule in rules)
    assert all(rule["sourceLinks"] for rule in rules)
    assert all(rule["execution"]["missingOutcome"] == "warn" for rule in rules)


def test_saved_rules_are_recontracted_server_side_and_report_unsupported_custom_checks():
    source_link = {
        "id": "chapter_88",
        "title": "Kansas City Zoning and Development Code Chapter 88",
        "url": "https://library.municode.com/mo/kansas_city/codes/zoning_and_development_code",
    }
    official, custom = _usable_custom_rules([
        {
            "id": "official",
            "rule": "Height",
            "condition": "Compare proposed height with the official maximum.",
            "source": "Chapter 88",
            "sourceIds": ["chapter_88"],
            "sourceLinks": [source_link],
            "checkType": "value_match",
            "execution": {"evaluator": "unsupported", "passRequiresEvidence": False},
        },
        {
            "id": "custom",
            "rule": "Owner preference",
            "condition": "Confirm the owner's preferred finish.",
            "source": "User-defined",
        },
    ])

    assert official["execution"]["evaluator"] == "evidence_grounded_value_comparator"
    assert official["execution"]["passRequiresEvidence"] is True
    assert official["implementation"]["status"] == "complete"
    assert custom["execution"]["evaluator"] == "unsupported"
    assert custom["implementation"]["status"] == "incomplete"


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
    active_permits = {item["id"] for item in active if item["application_kind"] == "permit"}
    assert active_permits == {
        567, 587, 618, 430, 576, 772, 435, 592, 442, 608
    }
    active_plans = {item["id"] for item in active if item["application_kind"] == "plan"}
    assert {644, 645, 647, 648, 649, 650, 651, 652, 653, 654, 655, 656, 667, 668} <= active_plans


def test_local_vector_index_searches_rules_without_deciding_applicability(tmp_path: Path):
    index_path = tmp_path / "kcmo.sqlite3"
    store = LocalKnowledgeVectorStore(index_path)
    count = store.rebuild(resolve_knowledge_root("kansas_city_mo"))
    results = store.search("1200 amp electrical service generator battery IB160", limit=10)

    assert count >= 200
    assert store.metadata()["authority_policy"] == "retrieval-only"
    assert any("electrical" in (result.title + " " + result.text).casefold() for result in results)
    assert any("ib160" in (result.title + " " + result.text).casefold() for result in results)
