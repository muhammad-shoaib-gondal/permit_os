from __future__ import annotations

import json
from collections import Counter

from shared.analysis.rule_coverage import catalog_implementation_report
from shared.tools.kcmo_review_rules import (
    expanded_review_rules,
    load_external_assessment_overlay,
)
from shared.tools.knowledge import resolve_knowledge_root


EXPECTED_EXCLUSIONS = {"P02-R05", "P05-R08", "P05-R20", "P18-R06"}


def test_every_external_assessment_item_has_an_auditable_disposition():
    overlay = load_external_assessment_overlay()
    rules = overlay["rules"]
    counts = Counter(rule["disposition"] for rule in rules)

    assert overlay["counts"] == {
        "permit_sections": 32,
        "permit_checks": 411,
        "cross_permit_checks": 12,
        "total": 423,
        "active": 360,
        "corrected": 59,
        "excluded": 4,
    }
    assert len(rules) == 423
    assert len({rule["external_id"] for rule in rules}) == 423
    assert sum(rule["section"] != "X" for rule in rules) == 411
    assert sum(rule["section"] == "X" for rule in rules) == 12
    assert counts == Counter(active=360, corrected=59, excluded=4)
    assert {rule["section"] for rule in rules if rule["section"] != "X"} == {
        f"P-{number:02d}" for number in range(1, 33)
    }


def test_exclusions_are_explicit_and_never_enter_runtime():
    overlay = load_external_assessment_overlay()
    excluded = [rule for rule in overlay["rules"] if rule["disposition"] == "excluded"]
    runtime_ids = {
        rule.get("externalAssessmentId") for rule in expanded_review_rules()
    }

    assert {rule["external_id"] for rule in excluded} == EXPECTED_EXCLUSIONS
    assert all(rule.get("reason", "").strip() for rule in excluded)
    assert EXPECTED_EXCLUSIONS.isdisjoint(runtime_ids)


def test_every_retained_assessment_rule_has_a_complete_runtime_path():
    overlay = load_external_assessment_overlay()
    expected = {
        rule["external_id"]
        for rule in overlay["rules"]
        if rule["disposition"] in {"active", "corrected"}
    }
    runtime = [
        rule for rule in expanded_review_rules() if rule.get("externalAssessmentId")
    ]
    report = catalog_implementation_report(runtime)

    assert len(runtime) == 419
    assert {rule["externalAssessmentId"] for rule in runtime} == expected
    assert report["total"] == 419
    assert report["complete"] == 419
    assert report["incomplete"] == 0
    assert all(rule["sourceLinks"] for rule in runtime)
    assert all(rule["execution"]["passRequiresEvidence"] is True for rule in runtime)
    assert all(rule["execution"]["missingOutcome"] == "warn" for rule in runtime)
    assert all(rule["implementation"]["status"] == "complete" for rule in runtime)


def test_overlay_sources_resolve_and_corrected_text_is_retained_for_audit():
    root = resolve_knowledge_root("kansas_city_mo")
    registry = json.loads((root / "source_registry.json").read_text(encoding="utf-8"))
    source_ids = {source["id"] for source in registry["sources"]}
    overlay = load_external_assessment_overlay()

    for rule in overlay["rules"]:
        assert rule["source_ids"]
        assert set(rule["source_ids"]) <= source_ids
        assert rule["citation"].strip()
        if rule["disposition"] == "corrected":
            assert rule["original_requirement"].strip()
            assert rule["original_requirement"] != rule["requirement"]


def test_obsolete_or_placeholder_requirements_are_not_executable():
    overlay = load_external_assessment_overlay()
    executable = " ".join(
        rule["requirement"]
        for rule in overlay["rules"]
        if rule["disposition"] in {"active", "corrected"}
    )

    assert "IECC 2018" not in executable
    assert "MO-R100" not in executable
    assert "MO-R10" not in executable
    assert "X ft" not in executable
    assert "X mph" not in executable
    assert "Y mph" not in executable
    assert "typ. 0 ft" not in executable
    assert "on Main St" not in executable
    assert "extremely rare downtown" not in executable


def test_state_stormwater_and_elevator_corrections_are_applied():
    overlay = load_external_assessment_overlay()
    by_id = {rule["external_id"]: rule for rule in overlay["rules"]}

    assert all(
        rule["permit_id"] == "modnr_construction_stormwater"
        for rule in overlay["rules"]
        if rule["section"] in {"P-30", "P-31"}
    )
    assert "MO-RA00000" in by_id["P30-R01"]["requirement"]
    assert "MO-RA00000" in by_id["P31-R01"]["requirement"]
    assert "Kansas City" in by_id["P28-R10"]["requirement"]
    assert "state installation plan review" in by_id["P28-R10"]["requirement"]


def test_cross_permit_invariants_are_ordered_after_permit_checks():
    runtime = [
        rule for rule in expanded_review_rules() if rule.get("externalAssessmentId")
    ]
    final_phase_indexes = [
        index
        for index, rule in enumerate(runtime)
        if rule["reviewPhase"] == "cross_permit_final"
    ]

    assert len(final_phase_indexes) == 12
    assert final_phase_indexes == list(range(len(runtime) - 12, len(runtime)))
    assert {runtime[index]["externalAssessmentId"] for index in final_phase_indexes} == {
        f"X-{number}" for number in range(1, 13)
    }
