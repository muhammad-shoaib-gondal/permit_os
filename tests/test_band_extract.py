"""Tests for Band message JSON extraction and report normalization."""

from uuid import UUID

from shared.band_client.messaging import parse_band_message
from shared.band_client.orchestrator import _extract_report
from shared.schemas.reports import JurisdictionReport

JURISDICTION_REPLY = """@PermitOS Conductor ```json
{
"type": "complete",
"case_id": "992e7fbb-dc0e-4499-be48-05b97b0c2261",
"agent": "jurisdiction",
"payload": {
"summary": "Multifamily at Riverside Dr.",
"readiness_impact": "not ready due to setback issue",
"checks": [
{
"check_name": "Setbacks",
"check_result": "8ft instead of required 10ft on Block B east wall.",
"check_citation": "Austin LDC 25-2-491"
}
],
"blockers": [
{
"blocker_name": "Side Setback Issue",
"blocker_description": "8ft vs 10ft required."
}
]
}
}
```"""


def test_parse_band_message_nested_payload():
    msg = parse_band_message(JURISDICTION_REPLY)
    assert msg is not None
    assert msg.agent == "jurisdiction"
    assert msg.payload["checks"][0]["check_name"] == "Setbacks"


def test_extract_jurisdiction_report_from_agent_reply():
    cid = UUID("992e7fbb-dc0e-4499-be48-05b97b0c2261")
    report = _extract_report(JURISDICTION_REPLY, "jurisdiction", JurisdictionReport, cid)
    assert report is not None
    assert report.case_id == cid
    assert len(report.checks) == 1
    assert report.checks[0].rule == "Setbacks"
    assert report.checks[0].status.value == "fail"
    assert report.blockers == ["8ft vs 10ft required."]
def test_extract_building_rejects_jurisdiction_reply():
    cid = UUID("992e7fbb-dc0e-4499-be48-05b97b0c2261")
    from shared.schemas.reports import BuildingSafetyReport

    report = _extract_report(JURISDICTION_REPLY, "building", BuildingSafetyReport, cid)
    assert report is None


def test_normalize_site_maps_generic_checks():
    from shared.band_client.report_normalize import normalize_site_payload

    cid = UUID("992e7fbb-dc0e-4499-be48-05b97b0c2261")
    out = normalize_site_payload(
        {
            "summary": "Site ok",
            "readiness_impact": "needs_changes",
            "checks": [
                {
                    "rule": "FEMA Flood Zone",
                    "status": "pass",
                    "citation": "FEMA",
                    "detail": "Zone X",
                }
            ],
        },
        cid,
    )
    assert len(out["environmental_checks"]) == 1
    assert out["environmental_checks"][0]["rule"] == "FEMA Flood Zone"

