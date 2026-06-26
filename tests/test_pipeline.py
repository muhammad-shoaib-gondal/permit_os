"""Schema and pipeline tests for PermitOS."""

from uuid import UUID

from shared.schemas.project_brief import ProjectBrief
from shared.tools.workflow import run_workflow_with_activity


def test_riverside_demo_pipeline():
    brief = ProjectBrief.riverside_residences_demo()
    result = run_workflow_with_activity(brief)

    assert result["jurisdiction_report"]["checks"]
    setback_fail = any(c["status"] == "fail" for c in result["jurisdiction_report"]["checks"])
    assert setback_fail

    assert result["case_summary"]["readiness_score"] == "NEEDS_CHANGES"
    assert result["permit_package"]["total_fees_estimate_usd"] == 47200
    assert result["permit_package"]["audit_hash"].startswith("sha256:")
    assert result.get("band_orchestrated") is False


def test_project_brief_schema():
    brief = ProjectBrief.riverside_residences_demo()
    assert brief.units == 50
    assert brief.blocks[0].block_id == "Block B"
    assert isinstance(brief.case_id, UUID)
