"""Tests for packager payload normalization."""

from uuid import UUID

from shared.band_client.report_normalize import normalize_packager_payload
from shared.schemas.package import PermitPackage

PACKAGER_STRING_LIST = {
    "permits_required": [
        "Building Permit",
        "Zoning Permit",
        "Flood Zone Permit",
        "Utility Capacity Permit",
    ],
    "documents_required": [
        "Site Plan",
        "Floor Plan",
    ],
    "filing_sequence": [
        "Building Permit",
        "Zoning Permit",
    ],
    "total_fees_estimate_usd": 10000,
}


def test_normalize_string_permit_lists():
    cid = UUID("e99793fc-3f28-4fc6-be44-d588b666eda1")
    data = normalize_packager_payload(PACKAGER_STRING_LIST, cid)
    pkg = PermitPackage.model_validate({**data, "case_id": str(cid)})
    assert len(pkg.permits_required) == 4
    assert pkg.permits_required[0].permit_name == "Building Permit"
    assert pkg.permits_required[0].fee_usd == 2500.0
    assert len(pkg.documents_required) == 2
    assert pkg.documents_required[0].name == "Site Plan"
