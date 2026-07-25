"""Fail-closed zoning checks for every classification returned by Overland Park GIS."""

from __future__ import annotations

import re
from typing import Any

from shared.analysis.rule_coverage import rule_implementation
from shared.analysis.rule_execution import attach_execution_contract

UDO_URL = "https://codes.opkansas.org/municipal-code/doc-view.aspx"
GIS_URL = "https://www.opkansas.gov/zoning-map"
COUNTY_URL = "https://www.jocogov.org/department/planning-housing-and-community-development/codes-and-regulations"

GIS_DISTRICTS = {
    "A", "A-J", "BP", "C-1", "C-2", "C-3", "C-O", "CP-1", "CP-1J", "CP-2", "CP-2J",
    "CP-3", "CP-3J", "CP-O", "CP-OJ", "DFD", "IP-1J", "IP-2J", "M-1", "M-2", "MP-1",
    "MP-2", "MXD", "PEC-2J", "PEC-3J", "PRB-1J", "PRB-2J", "PRB-3J", "PRLD-J", "PRN",
    "PRN-2J", "PRU-1AJ", "R-1", "R-1A", "R-1BJ", "R-2", "R-2J", "R-3", "R-4", "R-4J",
    "RE", "REC", "RLD-J", "RN-1J", "RN-2J", "ROW", "RP-1", "RP-1A", "RP-1N", "RP-2",
    "RP-3", "RP-4", "RP-5", "RP-6", "RP-OE", "RP-OS", "RR-J", "RUR-J",
}

DISTRICT_CHAPTERS = {
    "A": "18.160", "RE": "18.170", "RP-OE": "18.174", "RP-OS": "18.176",
    "R-1": "18.180", "RP-1": "18.180", "R-1A": "18.190", "RP-1A": "18.190",
    "RP-1N": "18.195", "R-2": "18.200", "RP-2": "18.200", "R-3": "18.210",
    "RP-3": "18.210", "R-4": "18.220", "RP-4": "18.220", "RP-5": "18.230",
    "RP-6": "18.240", "C-O": "18.250", "CP-O": "18.250", "C-1": "18.260",
    "CP-1": "18.260", "C-2": "18.270", "CP-2": "18.270", "MXD": "18.275",
    "C-3": "18.280", "CP-3": "18.280", "BP": "18.290", "M-1": "18.300",
    "MP-1": "18.300", "M-2": "18.310", "MP-2": "18.310", "PRN": "18.320",
    "DFD": "Downtown Form-Based Code",
}

PLAN_CONTROLLED = {district for district in GIS_DISTRICTS if district.startswith(("CP-", "MP-", "RP-", "PR")) or district in {"MXD", "DFD"}}
COUNTY_CARRIED = {district for district in GIS_DISTRICTS if district.endswith("J") or district.endswith("-J")}
LEGACY = {"R-4", "REC"}


def normalize_overland_park_district(value: str | None) -> str:
    return str(value or "").strip().upper()


def _rule(district: str, key: str, title: str, condition: str, check_type: str = "value_match", source_id: str = "udc", source_title: str = "Overland Park Unified Development Ordinance", source_url: str = UDO_URL, requires_values: bool = False) -> dict[str, Any]:
    rule = attach_execution_contract({
        "id": f"overland-park-zoning-{re.sub(r'[^a-z0-9]+', '-', district.casefold()).strip('-')}-{key}",
        "category": "zoning", "group": f"{district} zoning standards", "rule": title,
        "condition": condition, "severity": "blocker", "source": source_title,
        "sourceIds": [source_id], "sourceLinks": [{"id": source_id, "title": source_title, "url": source_url}],
        "checkType": check_type, "verifiedAt": "2026-07-23", "permitTypes": ["rezoning", "preliminary_plan_plat", "final_plan", "overland_park_rezoning", "overland_park_preliminary_plan_plat", "overland_park_final_plan"],
        "ruleFamilyIds": [], "requiresContextStandard": requires_values, "requiresResolvedStandardValues": requires_values,
    })
    return {**rule, "implementation": rule_implementation(rule)}


def _common_rules(district: str, chapter: str, source_id: str, source_title: str, source_url: str) -> list[dict[str, Any]]:
    prefix = f"Apply {chapter}" if chapter else "Apply every controlling district provision"
    return [
        _rule(district, "classification", "Official parcel zoning classification", "Verify the address, parcel, district, district name, category, ordinance, prior case, and code link against the official Overland Park GIS response.", "applicability", "zoning_map", "City of Overland Park Official Zoning Map", GIS_URL),
        _rule(district, "use", "Permitted, accessory, temporary, or special use", f"{prefix}: compare each proposed use with the controlling use provisions and require the applicable special-use or plan approval.", "value_match", source_id, source_title, source_url),
        _rule(district, "height-area", "Height and area regulations", f"{prefix}: extract and compare every applicable height, lot area, lot width, density, coverage, open-space, and setback standard with the survey, site plan, and elevations.", "value_match", source_id, source_title, source_url, True),
        _rule(district, "parking", "Parking, bicycle parking, stacking, and loading", "Calculate and compare all parking, accessible-space, bicycle, stacking, loading, shared-parking, and reduction requirements under the controlling code and approved plan.", "value_match", source_id, source_title, source_url, True),
        _rule(district, "design", "Site and architectural design standards", "Verify all adopted site, architectural, infill, redevelopment, commercial, multifamily, mixed-use, downtown, and area-specific standards that apply to the project.", "applicability", source_id, source_title, source_url),
        _rule(district, "landscape", "Landscaping, buffers, screening, lighting, and refuse", "Compare the landscape, buffer, street-tree, parking-lot, screening, refuse, mechanical-equipment, and exterior-lighting plans with every applicable standard.", "value_match", source_id, source_title, source_url, True),
        _rule(district, "access", "Access, circulation, sidewalks, and public facilities", "Verify vehicular and pedestrian access, circulation, sidewalks, streets, utilities, fire access and flow, drainage, easements, and adequate public facilities.", "cross_document", source_id, source_title, source_url),
        _rule(district, "signs", "Sign controls", "Verify each sign type, area, height, location, illumination, duration, permit, and coordinated sign-plan requirement under Chapter 18.440 and any approved plan.", "value_match", source_id, source_title, source_url, True),
        _rule(district, "environment", "Floodplain, stream corridor, and environmental overlays", "Resolve and apply floodplain, stream-corridor, stormwater, environmental, airport, and other overlay constraints before passing zoning review.", "applicability", source_id, source_title, source_url),
        _rule(district, "nonconforming", "Nonconforming status and vested approvals", "Determine whether any use, lot, structure, sign, or site condition is nonconforming and verify the proposed change is authorized by the controlling nonconformity and vested-right provisions.", "applicability", source_id, source_title, source_url),
        _rule(district, "cross-document", "Zoning values agree across project documents", "Verify district, legal description, use, dimensions, density, height, parking, access, and approved-plan values agree across the survey, site plan, civil plans, code analysis, and architectural set.", "cross_document", source_id, source_title, source_url),
    ]


def build_overland_park_rules(classification: str | None, zoning_profile: dict[str, Any] | None = None, project_type: str | None = None) -> list[dict[str, Any]]:
    del project_type
    district = normalize_overland_park_district(classification)
    if not district:
        return []
    if district in COUNTY_CARRIED:
        source_id, source_title, source_url = "joco_zoning", "Johnson County/Oxford Township carried zoning regulations", COUNTY_URL
        chapter = "the exact carried Johnson County or Oxford Township district standards identified by the GIS ZoningCode field"
    else:
        source_id, source_title, source_url = "udc", "Overland Park Unified Development Ordinance", UDO_URL
        chapter = DISTRICT_CHAPTERS.get(district, "Title 18 and the parcel-specific controlling approval")
    rules = _common_rules(district, chapter, source_id, source_title, source_url)
    attributes = (zoning_profile or {}).get("attributes") or {}
    if district in PLAN_CONTROLLED or district in LEGACY:
        rules.extend([
            _rule(district, "controlling-record", "Approved development plan, ordinance, and conditions", "Retrieve the binding preliminary and final development plans, ordinance, deviations, amendments, and conditions. Missing controlling records remain not verified.", "document_presence", source_id, source_title, source_url),
            _rule(district, "controlling-values", "Parcel-specific controlling values", "Extract every project-specific use, density, height, setback, parking, loading, open-space, access, infrastructure, architecture, landscape, phasing, and signage control before evaluating the proposal.", "value_match", source_id, source_title, source_url, True),
            _rule(district, "plan-match", "Proposal matches controlling approval", "Compare the current proposal with every binding approved-plan value and condition; a material deviation requires the applicable revised plan, deviation, or new approval.", "cross_document", source_id, source_title, source_url, True),
        ])
    if district == "ROW":
        rules.append(_rule(district, "row", "Right-of-way authorization", "Treat ROW as public right-of-way rather than a developable zoning district and require the applicable right-of-way, access, utility, traffic-control, and public-improvement approvals.", "applicability"))
    ordinance = str(attributes.get("Ordinance") or "").strip()
    prior_case = str(attributes.get("PriorCase") or "").strip()
    if ordinance or prior_case:
        label = ", ".join(value for value in (f"ordinance {ordinance}" if ordinance else "", f"prior case {prior_case}" if prior_case else "") if value)
        rules.append(_rule(district, "parcel-action", "Parcel-specific zoning action", f"Retrieve and apply {label}, including all approved plans, stipulations, deviations, and amendments.", "document_presence", source_id, source_title, source_url))
    if district not in GIS_DISTRICTS:
        rules.append(_rule(district, "unknown", "Unrecognized GIS classification", "Do not pass zoning review until Overland Park Planning confirms the classification and all controlling standards.", "applicability", "zoning_map", "City of Overland Park Official Zoning Map", GIS_URL, True))
    return list({rule["id"]: rule for rule in rules}.values())


def has_overland_park_rule_coverage(classification: str | None) -> bool:
    return normalize_overland_park_district(classification) in GIS_DISTRICTS
