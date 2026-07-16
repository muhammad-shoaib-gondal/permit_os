import pytest

from api.services import zoning_service


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
