from __future__ import annotations

import json

import pytest

from shared.analysis import custom_rules
from shared.schemas.project_brief import ProjectBrief
from shared.schemas.reports import CheckStatus
from shared.analysis.rule_execution import attach_execution_contract


def rule(*, check_type: str = "value_match", permit_type: str = "zoning_verification"):
    return {
        "id": "rule-1",
        "rule": "Floor area ratio compliance",
        "condition": "Compare proposed FAR with the controlling approved plan.",
        "category": "zoning",
        "source": "KCMO Chapter 88",
        "sourceLinks": [
            {
                "id": "chapter_88",
                "title": "KCMO Chapter 88",
                "url": "https://library.municode.com/mo/kansas_city/codes/zoning_and_development_code",
            }
        ],
        "sourceIds": ["chapter_88"],
        "verifiedAt": "2026-07-21",
        "checkType": check_type,
        "permitType": permit_type,
        "enabled": True,
    }


@pytest.mark.asyncio
async def test_rule_without_required_document_is_unverified_without_calling_llm(monkeypatch):
    async def unexpected_completion(*args, **kwargs):
        raise AssertionError("LLM should not run without required evidence")

    monkeypatch.setattr(custom_rules, "chat_completion", unexpected_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [rule(check_type="document_presence")],
        document_context=[],
        target_permit_types=["zoning_verification"],
    )

    assert len(results) == 1
    assert results[0].status == CheckStatus.WARN
    assert results[0].missing_inputs == ["document_inventory", "document_content"]


@pytest.mark.asyncio
async def test_model_pass_without_traceable_evidence_is_rejected(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps(
            [{"id": "rule-1", "status": "pass", "detail": "Complies", "evidence": []}]
        )

    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [rule()],
        document_context=[
            {
                "name": "site-plan.pdf",
                "document_type": "site_plan",
                "summary": "Site plan",
                "permit_types": ["zoning_verification"],
            }
        ],
        target_permit_types=["zoning_verification"],
    )

    assert results[0].status == CheckStatus.WARN
    assert "required evidence was not verified" in results[0].detail
    assert any("project document" in value for value in results[0].missing_inputs)


@pytest.mark.asyncio
async def test_cross_document_result_requires_two_distinct_sources(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps(
            [
                {
                    "id": "rule-1",
                    "status": "pass",
                    "detail": "Values match",
                    "evidence": [
                        {
                            "document": "site-plan.pdf",
                            "page": 1,
                            "detail": "Height 40 ft",
                            "source_type": "project_document",
                        }
                    ],
                }
            ]
        )

    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [rule(check_type="cross_document")],
        document_context=[
            {
                "name": "site-plan.pdf",
                "document_type": "site_plan",
                "summary": "Height 40 ft",
                "permit_types": ["zoning_verification"],
            }
        ],
        target_permit_types=["zoning_verification"],
    )

    assert results[0].status == CheckStatus.WARN
    assert results[0].missing_inputs == ["project document (2 required, 1 available)"]


@pytest.mark.asyncio
async def test_value_match_requires_standard_and_project_value(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps(
            [
                {
                    "id": "rule-1",
                    "status": "pass",
                    "detail": "FAR complies",
                    "evidence": [
                        {
                            "document": "site-plan.pdf",
                            "page": 1,
                            "detail": "Proposed FAR 2.0",
                            "source_type": "project_document",
                        }
                    ],
                }
            ]
        )

    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [rule()],
        document_context=[
            {
                "name": "site-plan.pdf",
                "document_type": "site_plan",
                "summary": "Proposed FAR 2.0",
                "permit_types": ["zoning_verification"],
            }
        ],
        target_permit_types=["zoning_verification"],
    )

    assert results[0].missing_inputs == []
    assert results[0].status == CheckStatus.PASS


@pytest.mark.asyncio
async def test_dynamic_zoning_value_cannot_pass_without_detected_standard(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps([{
            "id": "rule-1",
            "status": "pass",
            "detail": "FAR complies",
            "evidence": [{
                "document": "site-plan.pdf",
                "page": 1,
                "detail": "Proposed FAR 2.0",
                "source_type": "project_document",
            }],
        }])

    dynamic_rule = attach_execution_contract({
        **rule(),
        "requiresContextStandard": True,
    })
    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [dynamic_rule],
        document_context=[{
            "name": "site-plan.pdf",
            "document_type": "site_plan",
            "permit_types": ["zoning_verification"],
        }],
        target_permit_types=["zoning_verification"],
        authoritative_context={"zoningProfile": {}},
    )

    assert results[0].status == CheckStatus.WARN
    assert results[0].missing_inputs == [
        "authoritative standard (1 required, 0 available)"
    ]


@pytest.mark.asyncio
async def test_dynamic_zoning_value_uses_detected_profile_as_standard(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps([{
            "id": "rule-1",
            "status": "pass",
            "detail": "FAR complies",
            "evidence": [{
                "document": "site-plan.pdf",
                "page": 1,
                "detail": "Proposed FAR 2.0",
                "source_type": "project_document",
            }],
        }])

    dynamic_rule = attach_execution_contract({
        **rule(),
        "requiresContextStandard": True,
    })
    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [dynamic_rule],
        document_context=[{
            "name": "site-plan.pdf",
            "document_type": "site_plan",
            "permit_types": ["zoning_verification"],
        }],
        target_permit_types=["zoning_verification"],
        authoritative_context={
            "zoningProfile": {
                "classification": "UR",
                "standards": [{"key": "far", "value": 3.0}],
            }
        },
    )

    assert results[0].status == CheckStatus.PASS
    assert any(
        evidence["provider"] == "estatepermit_authoritative_context"
        for evidence in results[0].evidence
    )


@pytest.mark.asyncio
async def test_uploaded_agency_approval_can_supply_plan_controlled_standard(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps([{
            "id": "rule-1",
            "status": "pass",
            "detail": "The proposal matches the approved plan limit.",
            "evidence": [{
                "document": "approved-development-plan.pdf",
                "page": 4,
                "detail": "Approved maximum FAR is 2.5.",
                "source_type": "authoritative_standard",
            }, {
                "document": "site-plan.pdf",
                "page": 2,
                "detail": "Proposed FAR is 2.1.",
                "source_type": "project_document",
            }],
        }])

    dynamic_rule = attach_execution_contract({
        **rule(),
        "requiresContextStandard": True,
        "requiresResolvedStandardValues": True,
    })
    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [dynamic_rule],
        document_context=[{
            "name": "approved-development-plan.pdf",
            "document_type": "agency_approval",
            "permit_types": ["zoning_verification"],
        }, {
            "name": "site-plan.pdf",
            "document_type": "site_plan",
            "permit_types": ["zoning_verification"],
        }],
        target_permit_types=["zoning_verification"],
        authoritative_context={"zoningProfile": {"classification": "UR"}},
    )

    assert results[0].status == CheckStatus.PASS
    assert {
        evidence["provider"] for evidence in results[0].evidence
    } >= {"uploaded_official_approval_record", "uploaded_project_document"}


@pytest.mark.asyncio
async def test_fabricated_project_document_evidence_is_rejected(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps(
            [{
                "id": "rule-1",
                "status": "pass",
                "detail": "FAR complies",
                "evidence": [{
                    "document": "invented-plan.pdf",
                    "detail": "Proposed FAR 2.0",
                    "source_type": "project_document",
                }],
            }]
        )

    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [rule()],
        document_context=[{
            "name": "site-plan.pdf",
            "document_type": "site_plan",
            "permit_types": ["zoning_verification"],
        }],
        target_permit_types=["zoning_verification"],
    )

    assert results[0].status == CheckStatus.WARN
    assert any("project document" in value for value in results[0].missing_inputs)


@pytest.mark.asyncio
async def test_uploaded_license_record_can_supply_registry_evidence(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps(
            [{
                "id": "rule-1",
                "status": "pass",
                "detail": "License is active",
                "evidence": [{
                    "document": "mopro-result.pdf",
                    "detail": "License 123 is active",
                    "source_type": "authoritative_registry",
                }],
            }]
        )

    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [rule(check_type="credential")],
        document_context=[{
            "name": "mopro-result.pdf",
            "document_type": "license_record",
            "permit_types": ["zoning_verification"],
        }],
        target_permit_types=["zoning_verification"],
    )

    assert results[0].status == CheckStatus.PASS
    assert {item["sourceType"] for item in results[0].evidence} >= {
        "project_document",
        "authoritative_registry",
    }


@pytest.mark.asyncio
async def test_official_city_status_record_can_supply_sequencing_evidence(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps(
            [{
                "id": "rule-1",
                "status": "pass",
                "detail": "The prerequisite permit was issued before this step.",
                "evidence": [{
                    "document": "KCMO public record CPBC-1: issuance",
                    "detail": "Issue date 2026-07-01",
                    "source_type": "dated_status_record",
                }],
            }]
        )

    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [rule(check_type="sequencing")],
        document_context=[],
        target_permit_types=["zoning_verification"],
        authoritative_context={
            "externalRecords": {
                "evidence": [{
                    "document": "KCMO public record CPBC-1: issuance",
                    "detail": "Issue date 2026-07-01",
                    "sourceType": "dated_status_record",
                    "permitType": "zoning_verification",
                    "provider": "kcmo_open_data",
                }]
            }
        },
    )

    assert results[0].status == CheckStatus.PASS
    assert {item["sourceType"] for item in results[0].evidence} >= {
        "authoritative_standard",
        "dated_status_record",
    }


@pytest.mark.asyncio
async def test_city_contractor_registry_cannot_satisfy_professional_seal_rule(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps([{
            "id": "rule-1",
            "status": "pass",
            "detail": "Credential verified",
            "evidence": [{
                "document": "sealed-plan.pdf",
                "page": 1,
                "detail": "Missouri engineer seal",
                "source_type": "project_document",
            }, {
                "document": "KCMO active contractor directory: Acme",
                "detail": "Active contractor license",
                "source_type": "authoritative_registry",
            }],
        }])

    professional_rule = attach_execution_contract({
        **rule(check_type="credential"),
        "condition": "Verify the Missouri engineer professional seal and license.",
    })
    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [professional_rule],
        document_context=[{
            "name": "sealed-plan.pdf",
            "document_type": "architectural_plan",
            "permit_types": ["zoning_verification"],
        }],
        target_permit_types=["zoning_verification"],
        authoritative_context={"externalRecords": {"evidence": [{
            "document": "KCMO active contractor directory: Acme",
            "detail": "Active contractor license",
            "sourceType": "authoritative_registry",
            "provider": "kcmo_contractor_directory",
            "permitType": "zoning_verification",
        }] }},
    )

    assert results[0].status == CheckStatus.WARN
    assert any("authoritative registry" in value for value in results[0].missing_inputs)


@pytest.mark.asyncio
async def test_matching_city_contractor_registry_satisfies_trade_license_rule(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps([{
            "id": "rule-1",
            "status": "pass",
            "detail": "Trade license verified",
            "evidence": [{
                "document": "permit-application.pdf",
                "page": 1,
                "detail": "Acme Electric is the permit contractor",
                "source_type": "project_document",
            }, {
                "document": "KCMO active contractor directory: Acme Electric",
                "detail": "Active Electrical Contractor Class I license",
                "source_type": "authoritative_registry",
            }],
        }])

    trade_rule = attach_execution_contract({
        **rule(check_type="credential", permit_type="electrical"),
        "condition": "Verify the appropriately licensed electrical trade contractor.",
    })
    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [trade_rule],
        document_context=[{
            "name": "permit-application.pdf",
            "document_type": "application_form",
            "permit_types": ["electrical"],
        }],
        target_permit_types=["electrical"],
        authoritative_context={"externalRecords": {"evidence": [{
            "document": "KCMO active contractor directory: Acme Electric",
            "detail": "Active Electrical Contractor Class I license",
            "sourceType": "authoritative_registry",
            "provider": "kcmo_contractor_directory",
            "permitType": "electrical",
        }] }},
    )

    assert results[0].status == CheckStatus.PASS


@pytest.mark.asyncio
async def test_final_approval_rule_requires_status_for_every_required_permit(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps([{
            "id": "rule-1",
            "status": "pass",
            "detail": "All finals approved",
            "evidence": [{
                "document": "KCMO public record BUILD-1: final",
                "detail": "Building finaled 2026-07-20",
                "source_type": "dated_status_record",
            }],
        }])

    final_rule = attach_execution_contract({
        **rule(check_type="sequencing", permit_type="certificate_of_occupancy"),
        "rule": "All required final inspections approved",
        "condition": "All required final inspections must be approved before occupancy.",
    })
    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [final_rule],
        document_context=[],
        target_permit_types=["certificate_of_occupancy"],
        authoritative_context={
            "projectPermits": [
                {"permitType": "commercial_building", "requirementStatus": "required"},
                {"permitType": "electrical", "requirementStatus": "required"},
                {"permitType": "certificate_of_occupancy", "requirementStatus": "required"},
                {"permitType": "fire_alarm", "requirementStatus": "needs_confirmation"},
            ],
            "externalRecords": {"evidence": [{
                "document": "KCMO public record BUILD-1: final",
                "detail": "Building finaled 2026-07-20",
                "sourceType": "dated_status_record",
                "provider": "kcmo_open_data",
                "permitType": "commercial_building",
            }]},
        },
    )

    assert results[0].status == CheckStatus.WARN
    assert results[0].missing_inputs == [
        "dated final/status record for required permit: electrical"
    ]


@pytest.mark.asyncio
async def test_rules_are_limited_to_selected_permits(monkeypatch):
    async def fake_completion(*args, **kwargs):
        return json.dumps(
            [
                {
                    "id": "rule-1",
                    "status": "warn",
                    "detail": "Needs review",
                    "missing_inputs": ["actual value"],
                    "evidence": [],
                }
            ]
        )

    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        [rule(), {**rule(permit_type="electrical"), "id": "electrical-rule"}],
        document_context=[
            {
                "name": "site-plan.pdf",
                "document_type": "site_plan",
                "summary": "Site plan",
                "permit_types": ["zoning_verification"],
            }
        ],
        target_permit_types=["zoning_verification"],
    )

    assert len(results) == 1
    assert results[0].rule == "Floor area ratio compliance"


@pytest.mark.asyncio
async def test_large_rule_sets_are_batched_by_permit_without_losing_results(monkeypatch):
    calls: list[list[str]] = []

    async def fake_completion(_operation, messages, **_kwargs):
        prompt = messages[0]["content"][0]["text"]
        rules_payload = json.loads(prompt.split("Rules:\n", 1)[1])
        ids = [item["id"] for item in rules_payload]
        calls.append(ids)
        return json.dumps([
            {
                "id": item_id,
                "status": "warn",
                "detail": "Evidence is incomplete",
                "missing_inputs": ["supporting document"],
                "evidence": [],
            }
            for item_id in ids
        ])

    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    rules = [
        {
            **rule(permit_type="permit-a" if index < 20 else "permit-b"),
            "id": f"rule-{index}",
            "rule": f"Rule {index}",
        }
        for index in range(40)
    ]
    documents = [{
        "name": "complete-plan.pdf",
        "document_type": "architectural_plan",
        "permit_types": ["permit-a", "permit-b"],
    }]

    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        rules,
        document_context=documents,
        target_permit_types=["permit-a", "permit-b"],
    )

    assert len(calls) == 4
    assert all(len(batch) <= custom_rules.RULE_BATCH_SIZE for batch in calls)
    assert all(
        all(rule_id.startswith("rule-") for rule_id in batch)
        for batch in calls
    )
    assert len(results) == len(rules)
    assert [result.rule for result in results] == [f"Rule {index}" for index in range(40)]


@pytest.mark.asyncio
async def test_duplicate_rule_ids_receive_distinct_trace_ids(monkeypatch):
    async def fake_completion(_operation, messages, **_kwargs):
        prompt = messages[0]["content"][0]["text"]
        rules_payload = json.loads(prompt.split("Rules:\n", 1)[1])
        return json.dumps([
            {
                "id": item["id"],
                "status": "warn",
                "detail": "Needs evidence",
                "missing_inputs": ["document value"],
                "evidence": [],
            }
            for item in rules_payload
        ])

    monkeypatch.setattr(custom_rules, "chat_completion", fake_completion)
    duplicate_rules = [
        {**rule(), "rule": "First duplicate"},
        {**rule(), "rule": "Second duplicate"},
    ]
    results = await custom_rules.evaluate_custom_rules(
        ProjectBrief(project_name="Test", address="411 Main St"),
        duplicate_rules,
        document_context=[{
            "name": "site-plan.pdf",
            "document_type": "site_plan",
            "permit_types": ["zoning_verification"],
        }],
        target_permit_types=["zoning_verification"],
    )

    assert len(results) == 2
    assert [result.rule for result in results] == ["First duplicate", "Second duplicate"]
    assert len({result.rule_id for result in results}) == 2
