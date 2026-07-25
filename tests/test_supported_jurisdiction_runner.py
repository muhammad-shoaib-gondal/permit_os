import pytest

from shared.analysis import custom_rules
from shared.analysis.runner import run_analysis
from shared.schemas.project_brief import ProjectBrief, ProjectType
from shared.schemas.reports import CheckResult, CheckStatus


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("jurisdiction", "city_name"),
    [
        ("kansas_city_mo", "Kansas City, Missouri"),
        ("kansas_city_ks", "Kansas City, Kansas"),
        ("lenexa_ks", "Lenexa, Kansas"),
        ("overland_park_ks", "Overland Park, Kansas"),
    ],
)
async def test_supported_jurisdictions_never_emit_demo_findings(
    monkeypatch, jurisdiction, city_name
):
    async def fake_evaluate(*_args, **_kwargs):
        return [
            CheckResult(
                rule_id="permit-rule-1",
                rule="Permit-specific evidence check",
                status=CheckStatus.WARN,
                citation="Official jurisdiction source",
                detail="A required drawing value is not verified.",
                missing_inputs=["drawing value"],
            )
        ]

    monkeypatch.setattr(custom_rules, "evaluate_custom_rules", fake_evaluate)
    permit_type = "test_permit"
    result = await run_analysis(
        ProjectBrief(
            project_name="Supported project",
            address="100 Main St",
            jurisdiction=jurisdiction,
            project_type=ProjectType.COMMERCIAL,
            scope_of_work="new construction",
        ),
        custom_rules=[{
            "id": "permit-rule-1",
            "rule": "Permit-specific evidence check",
            "enabled": True,
            "permitType": permit_type,
        }],
        target_permit_types=[permit_type],
        authoritative_context={
            "zoningProfile": {"classification": "TEST"},
            "projectPermits": [{
                "permitType": permit_type,
                "permitName": "Test Permit",
                "issuingAuthority": city_name,
                "requirementStatus": "required",
                "requiredDocuments": ["sealed plans"],
                "estimatedFeeUsd": 125,
                "dependencies": [],
            }],
        },
    )

    assert result["jurisdiction_report"]["jurisdictions"][0]["name"] == city_name
    assert result["jurisdiction_report"]["checks"] == []
    assert result["building_report"]["checks"] == []
    assert result["site_report"]["environmental_checks"] == []
    assert "Austin" not in str(result)
    assert "MF-3" not in str(result)
    assert result["case_summary"]["readiness_score"] == "NEEDS_CHANGES"
    assert result["permit_package"]["permits_required"][0]["permit_name"] == "Test Permit"
    assert result["permit_package"]["total_fees_estimate_usd"] == 125
    assert result["custom_rules_report"]["checks"][0]["rule_id"] == "permit-rule-1"
