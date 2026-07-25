from __future__ import annotations

import pytest

from api.services import kcmo_controlling_records


@pytest.mark.asyncio
async def test_ur_record_lookup_returns_official_case_and_missing_public_plan(monkeypatch):
    monkeypatch.delenv("ZENMUX_API_KEY", raising=False)

    async def fake_get_json(url: str, params=None):
        if url.endswith("/Matters"):
            assert params == {"$filter": "MatterFile eq '050162'"}
            return [
                {
                    "MatterId": 44951,
                    "MatterGuid": "97533120-519C-4DA2-B573-AAD7565BE368",
                    "MatterTitle": "Approving a development plan. (10629-URD-8)",
                    "MatterStatusName": "Historical",
                }
            ]
        if url.endswith("/Attachments"):
            return [
                {
                    "MatterAttachmentId": 1,
                    "MatterAttachmentName": "Authenticated",
                    "MatterAttachmentHyperlink": "https://example.test/ordinance.pdf",
                    "MatterAttachmentShowOnInternetPage": True,
                }
            ]
        if url.endswith("/Histories"):
            return [
                {
                    "MatterHistoryActionName": "Passed as Substituted",
                    "MatterHistoryActionDate": "2005-03-03T15:00:00",
                }
            ]
        raise AssertionError(url)

    monkeypatch.setattr(kcmo_controlling_records, "_get_json", fake_get_json)
    record = await kcmo_controlling_records.resolve_ur_controlling_record("050162")

    assert record["lookupStatus"] == "found"
    assert record["caseNumber"] == "10629-URD-8"
    assert record["approvalAction"] == "Passed as Substituted"
    assert record["hasPublicApprovedPlan"] is False
    assert record["extractionStatus"] == "not_configured"
    assert record["standards"] == []
    assert record["officialUrl"] == "https://example.test/ordinance.pdf"


@pytest.mark.asyncio
async def test_ur_record_lookup_does_not_invent_record_without_ordinance():
    record = await kcmo_controlling_records.resolve_ur_controlling_record(None)

    assert record["lookupStatus"] == "missing_ordinance"
    assert record["standards"] == []


def test_public_record_url_falls_back_to_official_legistar_api():
    assert kcmo_controlling_records.public_record_url({"matterId": 44951, "attachments": []}) == (
        "https://webapi.legistar.com/v1/kansascity/Matters/44951"
    )
