from api.services.permit_review_service import (
    build_project_summary,
    detect_candidate_permits,
    get_required_documents,
)
from shared.schemas.project_brief import ProjectBrief, ProjectType


def test_detect_candidate_permits_for_seattle_ti():
    brief = ProjectBrief(
        project_name="Pine Street Retail Refresh",
        address="100 Pine St, Seattle, WA 98101",
        jurisdiction="seattle_wa",
        project_type=ProjectType.COMMERCIAL_TENANT_IMPROVEMENT,
        gross_sqft=4200,
        scope_of_work="Interior retail remodel with HVAC, electrical, plumbing, and fire alarm updates.",
        trade_scopes=["hvac", "electrical", "plumbing"],
        fire_alarm_work=True,
    )

    permits = detect_candidate_permits(brief)
    permit_keys = {permit.permit_key for permit in permits}

    assert "building_construction" in permit_keys
    assert "mechanical" in permit_keys
    assert "plumbing" in permit_keys
    assert "electrical" in permit_keys
    assert "fire_alarm_suppression" in permit_keys


def test_get_required_documents_for_building_permit():
    docs = get_required_documents("seattle_wa", "building_construction")
    labels = {doc.label for doc in docs}

    assert "Plan set" in labels
    assert "Code analysis" in labels


def test_build_project_summary_includes_scope_and_trades():
    brief = ProjectBrief(
        project_name="TI Demo",
        address="100 Pine St, Seattle, WA 98101",
        jurisdiction="seattle_wa",
        project_type=ProjectType.COMMERCIAL_TENANT_IMPROVEMENT,
        gross_sqft=2500,
        scope_of_work="Restaurant tenant improvement.",
        trade_scopes=["hvac", "kitchen_hood"],
    )

    summary = build_project_summary(brief)

    assert summary.city == "Seattle"
    assert "Restaurant tenant improvement." in summary.narrative
    assert any(fact.key == "trade_scopes" for fact in summary.facts)
