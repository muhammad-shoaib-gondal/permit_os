import pytest

from api.services import zoning_service
from api.services.project_service import _normalize_controlling_record, _public_project_warnings


@pytest.mark.asyncio
async def test_resolve_kcmo_address_and_zoning(monkeypatch):
    async def fake_arcgis_get(url, params):
        if url == zoning_service.GEOCODER_URL:
            return {
                "candidates": [
                    {
                        "address": "414 E 12th St, Kansas City, Missouri, 64106",
                        "score": 100,
                        "location": {"x": -94.5786, "y": 39.1001},
                        "attributes": {
                            "City": "Kansas City",
                            "Region": "MO",
                            "Postal": "64106",
                            "Addr_type": "PointAddress",
                        },
                    }
                ]
            }
        return {
            "features": [
                {
                    "attributes": {
                        "CLASSIFICATION": "DC-15",
                        "LANDUSE": "Commercial",
                        "ORD_NO": "220997",
                    }
                }
            ]
        }

    monkeypatch.setattr(zoning_service, "_arcgis_get", fake_arcgis_get)

    result = await zoning_service.resolve_zoning(
        "414 E 12th St, Kansas City, MO 64106", "kansas_city_mo"
    )

    assert result["status"] == "resolved"
    assert result["profile"]["district"] == "DC-15"
    assert result["profile"]["matchedAddress"].startswith("414 E 12th")
    assert result["profile"]["sourceUrl"] == (
        "https://maps.kcmo.org/apps/parcelviewer/"
        "?address=414+E+12th+St%2C+Kansas+City%2C+MO+64106"
    )
    assert not any(warning["code"] == "numeric_rules_missing" for warning in result["warnings"])


@pytest.mark.asyncio
async def test_resolve_manhattan_commercial_zone_without_missing_rules_warning(monkeypatch):
    async def fake_arcgis_get(url, params):
        if url == zoning_service.GEOCODER_URL:
            return {
                "candidates": [
                    {
                        "address": "100 Manhattan Town Center, Manhattan, Kansas, 66502",
                        "score": 100,
                        "location": {"x": -96.5589, "y": 39.1797},
                        "attributes": {
                            "City": "Manhattan",
                            "Region": "KS",
                            "Postal": "66502",
                            "Addr_type": "PointAddress",
                        },
                    }
                ]
            }
        return {
            "features": [
                {
                    "attributes": {
                        "ZONINGTYPE": "CD",
                        "ZONINGNAME": "Downtown",
                        "DEVTYPE": "Unknown",
                        "ORDINANCE": "7794",
                        "PUDTYPE": "Unknown",
                    }
                }
            ]
        }

    monkeypatch.setattr(zoning_service, "_arcgis_get", fake_arcgis_get)

    result = await zoning_service.resolve_zoning(
        "100 Manhattan Town Center, Manhattan, KS 66502", "manhattan_ks"
    )

    assert result["status"] == "resolved"
    assert result["profile"]["district"] == "CD"
    assert not any(warning["code"] == "numeric_rules_missing" for warning in result["warnings"])


@pytest.mark.asyncio
async def test_incomplete_address_returns_actionable_warning_without_lookup(monkeypatch):
    async def unexpected_lookup(url, params):
        raise AssertionError("Incomplete addresses must not reach the geocoder")

    monkeypatch.setattr(zoning_service, "_arcgis_get", unexpected_lookup)

    result = await zoning_service.resolve_zoning("414 E 12th St", "kansas_city_mo")

    assert result["status"] == "invalid_address"
    assert result["warnings"] == [
        {
            "code": "address_incomplete",
            "message": "The address is not complete enough to locate a parcel.",
            "action": "Enter a street number, street name, city, state, and ZIP code.",
            "severity": "error",
        }
    ]


@pytest.mark.asyncio
async def test_address_in_wrong_city_is_rejected(monkeypatch):
    async def fake_arcgis_get(url, params):
        return {
            "candidates": [
                {
                    "address": "414 E 12th St, Kansas City, Kansas, 66102",
                    "score": 99,
                    "location": {"x": -94.62, "y": 39.11},
                    "attributes": {
                        "City": "Kansas City",
                        "Region": "KS",
                        "Postal": "66102",
                        "Addr_type": "PointAddress",
                    },
                }
            ]
        }

    monkeypatch.setattr(zoning_service, "_arcgis_get", fake_arcgis_get)

    result = await zoning_service.resolve_zoning(
        "414 E 12th St, Kansas City, MO 64106", "kansas_city_mo"
    )

    assert result["status"] == "invalid_address"
    assert result["warnings"][0]["code"] == "wrong_city"


@pytest.mark.asyncio
async def test_operational_errors_do_not_expose_exception_details(monkeypatch):
    async def failed_lookup(url, params):
        raise RuntimeError("ZENMUX_API_KEY missing at C:\\private\\app.env")

    monkeypatch.setattr(zoning_service, "_arcgis_get", failed_lookup)

    result = await zoning_service.resolve_zoning(
        "414 E 12th St, Kansas City, MO 64106", "kansas_city_mo"
    )

    warning_text = " ".join(
        f"{warning['message']} {warning['action']}" for warning in result["warnings"]
    ).casefold()
    assert "zenmux" not in warning_text
    assert "api_key" not in warning_text
    assert "private" not in warning_text


@pytest.mark.asyncio
async def test_ur_missing_ai_configuration_is_not_a_project_warning(monkeypatch):
    async def fake_arcgis_get(url, params):
        if url == zoning_service.GEOCODER_URL:
            return {
                "candidates": [
                    {
                        "address": "411 Main St, Kansas City, Missouri, 64105",
                        "score": 100,
                        "location": {"x": -94.583, "y": 39.108},
                        "attributes": {
                            "City": "Kansas City",
                            "Region": "MO",
                            "Postal": "64105",
                            "Addr_type": "PointAddress",
                        },
                    }
                ]
            }
        return {
            "features": [
                {
                    "attributes": {
                        "CLASSIFICATION": "UR",
                        "LANDUSE": "Commercial",
                        "ORD_NO": "050162",
                    }
                }
            ]
        }

    async def no_context(address, location, profile):
        return None

    async def fake_record(ordinance):
        return {
            "ordinance": ordinance,
            "lookupStatus": "found",
            "caseNumber": "10629-URD-8",
            "hasPublicApprovedPlan": False,
            "extractionStatus": "not_configured",
            "standards": [],
            "attachments": [],
        }

    monkeypatch.setattr(zoning_service, "_arcgis_get", fake_arcgis_get)
    monkeypatch.setattr(zoning_service, "_enrich_kcmo_permit_context", no_context)
    monkeypatch.setattr(zoning_service, "resolve_ur_controlling_record", fake_record)

    result = await zoning_service.resolve_zoning(
        "411 Main St, Kansas City, MO 64105", "kansas_city_mo"
    )

    assert not any(
        warning["code"] == "ur_record_extraction_unavailable"
        for warning in result["warnings"]
    )
    assert not any("zenmux" in warning["message"].casefold() for warning in result["warnings"])


def test_serialized_project_warnings_hide_legacy_internal_details():
    warnings = _public_project_warnings(
        [
            {
                "code": "ur_record_extraction_unavailable",
                "message": "ZenMux is not configured.",
                "action": "Set ZENMUX_API_KEY in C:\\private\\.env.",
                "severity": "warning",
            },
            {
                "code": "future_operational_warning",
                "message": "Backend exception: provider unavailable.",
                "action": "Inspect localhost logs.",
                "severity": "warning",
            },
        ]
    )

    assert len(warnings) == 1
    warning_text = f"{warnings[0]['message']} {warnings[0]['action']}".casefold()
    assert "backend" not in warning_text
    assert "exception" not in warning_text
    assert "localhost" not in warning_text


def test_public_controlling_record_hides_extraction_diagnostics():
    profile = {
        "controllingRecord": {
            "matterId": 44951,
            "extractionStatus": "not_configured",
            "attachments": [
                {
                    "name": "Authenticated",
                    "kind": "ordinance",
                    "url": "https://example.test/ordinance.pdf",
                    "extractionStatus": "failed",
                }
            ],
        }
    }

    _normalize_controlling_record(profile)

    record = profile["controllingRecord"]
    assert record["officialUrl"] == "https://example.test/ordinance.pdf"
    assert "extractionStatus" not in record
    assert "extractionStatus" not in record["attachments"][0]
