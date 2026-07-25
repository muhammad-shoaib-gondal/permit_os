from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.services import kcmo_external_records


@pytest.mark.asyncio
async def test_permit_lookup_builds_dated_evidence_from_official_datasets(monkeypatch):
    async def fake_rows(dataset: str, field: str, permit_number: str):
        assert permit_number == "CPBC-2026-001"
        if dataset == kcmo_external_records.CITY_PERMITS_DATASET:
            return [{"permit_status": "Issued", "issue_date": "2026-07-01"}]
        if dataset == kcmo_external_records.STATUS_HISTORY_DATASET:
            return [{
                "statusprevious": "In Review",
                "statuscurrent": "Issued",
                "statuspreviousdate": "2026-07-01",
            }]
        return []

    monkeypatch.setattr(kcmo_external_records, "_permit_dataset_rows", fake_rows)
    result = await kcmo_external_records.lookup_permit_record("CPBC-2026-001")

    assert result["lookupStatus"] == "found"
    assert len(result["evidence"]) == 2
    assert {item["sourceType"] for item in result["evidence"]} == {"dated_status_record"}
    assert all(item["provider"] == "kcmo_open_data" for item in result["evidence"])


@pytest.mark.asyncio
async def test_contractor_lookup_requires_a_strong_company_name_match(monkeypatch):
    async def fake_contractors(license_type: str):
        return [{
            "company name": "Acme Fire Protection LLC",
            "license #": "LIC-42",
            "license expires": "12/31/2026",
        }]

    monkeypatch.setattr(kcmo_external_records, "_contractors_for_license_type", fake_contractors)
    exact = await kcmo_external_records.lookup_contractor(
        "Acme Fire Protection LLC", "fire_sprinkler"
    )
    short = await kcmo_external_records.lookup_contractor("Acme", "fire_sprinkler")

    assert exact["lookupStatus"] == "found"
    assert exact["evidence"][0]["sourceType"] == "authoritative_registry"
    assert short["lookupStatus"] == "not_found"


@pytest.mark.asyncio
async def test_external_collection_does_not_query_without_identifiers(monkeypatch):
    async def unexpected(*args, **kwargs):
        raise AssertionError("No external lookup should run without an identifier")

    monkeypatch.setattr(kcmo_external_records, "lookup_permit_record", unexpected)
    monkeypatch.setattr(kcmo_external_records, "lookup_contractor", unexpected)
    permit = SimpleNamespace(
        permit_type="building",
        application_number=None,
        issued_number=None,
        assigned_contractor=None,
    )

    result = await kcmo_external_records.collect_external_records([permit])

    assert result["evidence"] == []
    assert result["professionalLicenseProvider"]["lookupStatus"] == "interactive_only"
