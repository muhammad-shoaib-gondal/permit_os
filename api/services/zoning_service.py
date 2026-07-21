from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from api.services.kcmo_zoning_rules import has_kcmo_rule_coverage
from api.services.manhattan_zoning_rules import has_manhattan_rule_coverage
from shared.tools.knowledge import load_json

GEOCODER_URL = (
    "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/"
    "findAddressCandidates"
)

JURISDICTION_ZONING = {
    "manhattan_ks": {
        "city": "Manhattan",
        "city_aliases": {"manhattan"},
        "regions": {"Kansas", "KS"},
        "source_name": "City of Manhattan Zoning Districts GIS",
        "source_url": "https://gis.cityofmhk.com/mhkserver/rest/services/Public/Zoning/FeatureServer/2",
        "query_url": "https://gis.cityofmhk.com/mhkserver/rest/services/Public/Zoning/FeatureServer/2/query",
        "out_fields": "ZONINGTYPE,ZONINGNAME,DEVTYPE,PUDNAME,PUDTYPE,ORDINANCE,ORDDOC",
        "district_field": "ZONINGTYPE",
        "district_name_field": "ZONINGNAME",
        "land_use_field": "DEVTYPE",
        "ordinance_field": "ORDINANCE",
        "extra_fields": ["PUDNAME", "PUDTYPE", "ORDDOC"],
    },
    "kansas_city_mo": {
        "city": "Kansas City",
        "city_aliases": {"kansas city", "kcmo"},
        "regions": {"Missouri", "MO"},
        "source_name": "Kansas City, Missouri Parcel Viewer Zoning GIS",
        "source_url": "https://maps.kcmo.org/apps/parcelviewer/",
        "source_address_param": "address",
        "query_url": "https://mapd.kcmo.org/kcgis/rest/services/maps/Zoning/MapServer/0/query",
        "out_fields": "CLASSIFICATION,LANDUSE,ORD_NO",
        "district_field": "CLASSIFICATION",
        "district_name_field": "LANDUSE",
        "land_use_field": "LANDUSE",
        "ordinance_field": "ORD_NO",
        "extra_fields": [],
    },
    "kansas_city_ks": {
        "city": "Kansas City",
        "city_aliases": {"kansas city", "kck"},
        "regions": {"Kansas", "KS"},
        "source_name": "Unified Government Kansas City, Kansas Zoning GIS",
        "source_url": "https://gisweb.wycokck.org/arcgis/rest/services/GISPUB/Kansas_City_Ks_Zoning/FeatureServer/0",
        "query_url": "https://gisweb.wycokck.org/arcgis/rest/services/GISPUB/Kansas_City_Ks_Zoning/FeatureServer/0/query",
        "out_fields": "ZONEDIST,ZONENAME,ORD_NO1,ORD_NO2,ORD_NO3,SPLIT_ZONE,HISTORIC,ENVIRONS,ZONING_LABEL",
        "district_field": "ZONEDIST",
        "district_name_field": "ZONENAME",
        "land_use_field": "ZONENAME",
        "ordinance_field": "ORD_NO1",
        "extra_fields": ["ORD_NO2", "ORD_NO3", "SPLIT_ZONE", "HISTORIC", "ENVIRONS", "ZONING_LABEL"],
        "advisory": "The Unified Government GIS layer is a planning reference; confirm the official zoning classification before filing.",
    },
    "seattle_wa": {
        "city": "Seattle",
        "city_aliases": {"seattle"},
        "regions": {"Washington", "WA"},
        "source_name": "City of Seattle Current Land Use Zoning GIS",
        "source_url": (
            "https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/"
            "Mandatory_Housing_Affordability_Zoning/FeatureServer/0"
        ),
        "query_url": (
            "https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/"
            "Mandatory_Housing_Affordability_Zoning/FeatureServer/0/query"
        ),
        "out_fields": (
            "ZONING,BASE_ZONE,ZONING_DESC,HISTORIC,PEDESTRIAN,SHORELINE,OVERLAY,"
            "LIGHTRAIL,MHA,IZ,CHAPTER,CHAPTER_LINK,ORDINANCE"
        ),
        "district_field": "ZONING",
        "district_name_field": "ZONING_DESC",
        "land_use_field": "ZONING_DESC",
        "ordinance_field": "ORDINANCE",
        "extra_fields": [
            "BASE_ZONE",
            "HISTORIC",
            "PEDESTRIAN",
            "SHORELINE",
            "OVERLAY",
            "LIGHTRAIL",
            "MHA",
            "IZ",
            "CHAPTER",
            "CHAPTER_LINK",
        ],
        "advisory": (
            "Seattle identifies this GIS layer as a planning reference rather than an official zoning verification."
        ),
    },
}


def public_zoning_source_url(jurisdiction: str, address: str) -> str | None:
    config = JURISDICTION_ZONING.get(jurisdiction)
    if not config:
        return None
    source_url = str(config["source_url"])
    address_param = config.get("source_address_param")
    if address_param:
        return f"{source_url}?{urlencode({address_param: address})}"
    return source_url


def _warning(code: str, message: str, action: str, severity: str = "warning") -> dict[str, str]:
    return {"code": code, "message": message, "action": action, "severity": severity}


async def _enrich_kcmo_permit_context(
    address: str, location: dict[str, Any], profile: dict[str, Any]
) -> None:
    base = "https://mapd.kcmo.org/kcgis/rest/services/AGOL/MapServer"
    layers = {
        "parcels": (6, "KIVAPIN,APN,PLATNAME,LOT,BLOCK,ADDRESS,LEGAL"),
        "historicLocal": (19, "NAME,ADDRESS,CASE_NO,STATUS,REGISTER"),
        "historicNational": (20, "NAME,ADDRESS,REGISTER"),
        "plats": (24, "PLATNUMBER,PLATNAME,STATUS,PLANNUMBER"),
        "developmentCases": (25, "PLANNUMBER,PLANTYPE,STATUS,DESCRIPTION,PROJECTNAME"),
        "verifiedLots": (26, "ID,KIVAPIN,LEGAL,Lot_Number,Lot_Area"),
        "overlays": (28, "OVERLAYDISTRICT,NAME,ORD_NO,ENERGOVZONE"),
    }

    async def query(layer_id: int, out_fields: str) -> dict[str, Any]:
        return await _arcgis_get(
            f"{base}/{layer_id}/query",
            {
                "f": "json",
                "geometry": f"{location['x']},{location['y']}",
                "geometryType": "esriGeometryPoint",
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": out_fields,
                "returnGeometry": "false",
            },
        )

    results = await asyncio.gather(
        *(query(layer_id, fields) for layer_id, fields in layers.values()),
        return_exceptions=True,
    )
    rows: dict[str, list[dict[str, Any]]] = {}
    failures: list[str] = []
    for key, result in zip(layers, results):
        if isinstance(result, Exception):
            failures.append(key)
            continue
        rows[key] = [feature.get("attributes") or {} for feature in result.get("features", [])]

    normalized = " ".join(address.casefold().replace(",", " ").split())
    latitude = profile.get("latitude")
    longitude = profile.get("longitude")
    try:
        in_streetcar_bounds = (
            38.95 <= float(latitude) <= 39.12
            and -94.60 <= float(longitude) <= -94.57
            and bool(re.search(r"\bmain\s+(st|street)\b", normalized))
        )
    except (TypeError, ValueError):
        in_streetcar_bounds = False

    context: dict[str, Any] = {
        "version": 1,
        "lookupStatus": "partial" if failures else "complete",
        "failedLookups": failures,
        "nearStreetcar": in_streetcar_bounds,
    }
    if "parcels" in rows:
        context["parcelCount"] = len(rows["parcels"])
        context["parcels"] = rows["parcels"]
    if "historicLocal" in rows:
        context["historicLocal"] = bool(rows["historicLocal"])
        context["historicLocalRecords"] = rows["historicLocal"]
    if "historicNational" in rows:
        context["historicNational"] = bool(rows["historicNational"])
        context["historicNationalRecords"] = rows["historicNational"]
    if "plats" in rows:
        context["platCount"] = len(rows["plats"])
        context["plats"] = rows["plats"]
    if "developmentCases" in rows:
        context["developmentCaseCount"] = len(rows["developmentCases"])
        context["developmentCases"] = rows["developmentCases"]
    if "verifiedLots" in rows:
        context["verifiedLotCount"] = len(rows["verifiedLots"])
        context["verifiedLots"] = rows["verifiedLots"]
    if "overlays" in rows:
        context["overlays"] = rows["overlays"]
    profile["permitContext"] = context


async def _arcgis_get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"].get("message", "ArcGIS request failed"))
    return payload


def _address_looks_complete(address: str, config: dict[str, Any]) -> bool:
    normalized = " ".join(address.casefold().replace(",", " ").split())
    has_street_number = bool(re.search(r"\b\d+[A-Za-z]?\b", address))
    has_zip = bool(re.search(r"\b\d{5}(?:-\d{4})?\b", address))
    has_city = any(alias.casefold() in normalized for alias in config["city_aliases"])
    has_region = any(re.search(rf"\b{re.escape(region.casefold())}\b", normalized) for region in config["regions"])
    return has_street_number and has_zip and has_city and has_region


def has_zoning_rule_coverage(jurisdiction: str, district: str | None) -> bool:
    if not district:
        return False
    if jurisdiction == "kansas_city_mo":
        return has_kcmo_rule_coverage(district)
    if jurisdiction == "manhattan_ks":
        return has_manhattan_rule_coverage(district)
    try:
        zoning = load_json("zoning_rules.json", jurisdiction)
    except Exception:
        return False
    districts = zoning.get("districts") or zoning.get("residential_districts") or {}
    return district in districts or district.upper() in districts


def _rule_coverage_warning(jurisdiction: str, district: str) -> dict[str, str] | None:
    try:
        zoning = load_json("zoning_rules.json", jurisdiction)
    except Exception:
        return _warning(
            "numeric_rules_missing",
            f"Zoning district {district} was detected, but its numeric height, setback, parking, and coverage rules are not loaded yet.",
            "Use the detected district as a starting point and verify development standards with the cited city code.",
        )

    if not has_zoning_rule_coverage(jurisdiction, district):
        return _warning(
            "numeric_rules_missing",
            f"Zoning district {district} was detected, but EstatePermit does not yet have complete numeric rules for that district.",
            "EstatePermit will defer unsupported district checks instead of asking you to supply rule values.",
        )
    return None


async def resolve_zoning(address: str, jurisdiction: str) -> dict[str, Any]:
    config = JURISDICTION_ZONING.get(jurisdiction)
    resolved_at = datetime.now(timezone.utc).isoformat()
    if not config:
        return {
            "status": "unsupported",
            "profile": {"resolvedAt": resolved_at},
            "warnings": [
                _warning(
                    "unsupported_jurisdiction",
                    "Automatic zoning is not configured for this city.",
                    "Choose Kansas City, Kansas; Kansas City, Missouri; Manhattan; or Seattle.",
                    "error",
                )
            ],
        }

    if not _address_looks_complete(address, config):
        return {
            "status": "invalid_address",
            "profile": {"resolvedAt": resolved_at},
            "warnings": [
                _warning(
                    "address_incomplete",
                    "The address is not complete enough to locate a parcel.",
                    "Enter a street number, street name, city, state, and ZIP code.",
                    "error",
                )
            ],
        }

    try:
        geocode = await _arcgis_get(
            GEOCODER_URL,
            {
                "SingleLine": address,
                "f": "json",
                "outFields": "Match_addr,Addr_type,City,Region,Postal",
                "outSR": 4326,
                "maxLocations": 3,
            },
        )
    except Exception as exc:
        return {
            "status": "service_unavailable",
            "profile": {"resolvedAt": resolved_at},
            "warnings": [
                _warning(
                    "geocoder_unavailable",
                    f"The address lookup service could not be reached: {exc}",
                    "Retry zoning resolution. Permit recommendations remain preliminary until the address is resolved.",
                    "error",
                )
            ],
        }

    candidates = geocode.get("candidates") or []
    if not candidates:
        return {
            "status": "invalid_address",
            "profile": {"resolvedAt": resolved_at},
            "warnings": [
                _warning(
                    "address_not_found",
                    "No matching address was found.",
                    "Check the street number, spelling, city, state, and ZIP code.",
                    "error",
                )
            ],
        }

    candidate = candidates[0]
    attrs = candidate.get("attributes") or {}
    location = candidate.get("location") or {}
    score = float(candidate.get("score") or 0)
    matched_city = str(attrs.get("City") or "").strip()
    matched_region = str(attrs.get("Region") or "").strip()
    warnings: list[dict[str, str]] = []
    profile: dict[str, Any] = {
        "inputAddress": address,
        "matchedAddress": candidate.get("address") or attrs.get("Match_addr"),
        "matchScore": score,
        "addressType": attrs.get("Addr_type"),
        "city": matched_city,
        "region": matched_region,
        "postalCode": attrs.get("Postal"),
        "latitude": location.get("y"),
        "longitude": location.get("x"),
        "sourceName": config["source_name"],
        "sourceUrl": public_zoning_source_url(jurisdiction, address),
        "resolvedAt": resolved_at,
    }

    if matched_city.casefold() != config["city"].casefold() or matched_region not in config["regions"]:
        warnings.append(
            _warning(
                "wrong_city",
                f"The address resolved to {matched_city or 'an unknown city'}, {matched_region or 'unknown state'}, not {config['city']}.",
                "Correct the address or select the matching jurisdiction.",
                "error",
            )
        )
        return {"status": "invalid_address", "profile": profile, "warnings": warnings}

    if score < 90:
        warnings.append(
            _warning(
                "low_address_confidence",
                f"The address match confidence is only {score:.0f}%.",
                "Confirm the matched address before relying on the zoning result.",
            )
        )

    try:
        zoning = await _arcgis_get(
            config["query_url"],
            {
                "f": "json",
                "geometry": f"{location['x']},{location['y']}",
                "geometryType": "esriGeometryPoint",
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": config["out_fields"],
                "returnGeometry": "false",
            },
        )
    except Exception as exc:
        warnings.append(
            _warning(
                "zoning_service_unavailable",
                f"The city zoning service could not be reached: {exc}",
                "Retry zoning resolution. Permit recommendations remain preliminary until zoning is resolved.",
                "error",
            )
        )
        return {"status": "service_unavailable", "profile": profile, "warnings": warnings}

    features = zoning.get("features") or []
    rows = [feature.get("attributes") or {} for feature in features]
    districts = sorted(
        {str(row.get(config["district_field"])).strip() for row in rows if row.get(config["district_field"])}
    )
    profile["districts"] = districts
    if not districts:
        warnings.append(
            _warning(
                "zoning_not_found",
                "The address was found, but no zoning polygon matched its location.",
                "Confirm the parcel location or contact the city zoning office.",
                "error",
            )
        )
        return {"status": "zoning_not_found", "profile": profile, "warnings": warnings}

    if len(districts) > 1:
        warnings.append(
            _warning(
                "split_zoning",
                f"The location intersects multiple zoning districts: {', '.join(districts)}.",
                "Confirm which parcel or project boundary applies before running zoning review.",
            )
        )

    row = rows[0]
    district = "/".join(districts)
    profile.update(
        {
            "district": district,
            "districtName": row.get(config["district_name_field"]),
            "landUse": row.get(config["land_use_field"]),
            "ordinance": row.get(config["ordinance_field"]),
            "attributes": {field: row.get(field) for field in config["extra_fields"] if row.get(field) not in (None, "", " ")},
        }
    )

    if jurisdiction == "kansas_city_mo":
        await _enrich_kcmo_permit_context(address, location, profile)

    advisory = config.get("advisory")
    if advisory:
        warnings.append(
            _warning(
                "advisory_zoning_source",
                advisory,
                "Verify precise zoning with the city before filing.",
                "info",
            )
        )

    coverage_warning = _rule_coverage_warning(jurisdiction, district)
    if coverage_warning:
        warnings.append(coverage_warning)

    status = "resolved_with_warnings" if warnings else "resolved"
    return {"status": status, "profile": profile, "warnings": warnings}
