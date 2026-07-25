import pytest

from api.models import Project
from api.services.project_service import DEFAULT_SCOPE, _sync_project_permit_recommendations
from shared.analysis.jurisdiction_coverage import build_jurisdiction_coverage_report


def test_supported_jurisdiction_coverage_contract_is_complete():
    report = build_jurisdiction_coverage_report()

    assert report["complete"], report
    assert report["jurisdictions"]["kansas_city_mo"]["workflowCount"] == 241
    assert report["jurisdictions"]["kansas_city_ks"]["workflowCount"] == 91
    assert report["jurisdictions"]["lenexa_ks"]["workflowCount"] == 83
    assert report["jurisdictions"]["overland_park_ks"]["workflowCount"] == 85
    assert all(
        jurisdiction["minimumRulesPerWorkflow"] >= 10
        for jurisdiction in report["jurisdictions"].values()
    )


@pytest.mark.parametrize(
    ("jurisdiction", "address", "expected_count"),
    [
        ("kansas_city_mo", "414 E 12th St, Kansas City, MO 64106", 241),
        ("kansas_city_ks", "701 N 7th St, Kansas City, KS 66101", 91),
        ("lenexa_ks", "17101 W 87th St Pkwy, Lenexa, KS 66219", 83),
        ("overland_park_ks", "8500 Santa Fe Dr, Overland Park, KS 66212", 85),
    ],
)
def test_all_scope_project_persists_every_workflow_and_questions_unknowns(
    jurisdiction, address, expected_count
):
    project = Project(
        project_id=f"all-scope-{jurisdiction}",
        name="All-scope adversarial fixture",
        address=address,
        project_type="mixed_use",
        jurisdiction=jurisdiction,
        scope={key: True for key in DEFAULT_SCOPE},
        permit_answers={},
        custom_rules=[],
        permits=[],
    )

    _sync_project_permit_recommendations(project)

    assert len(project.permits) == expected_count
    assert len({permit.permit_type for permit in project.permits}) == expected_count
    assert all(
        permit.requirement_status != "needs_confirmation"
        or permit.recommendation_evidence.get("questions")
        for permit in project.permits
    )
