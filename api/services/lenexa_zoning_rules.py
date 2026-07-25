"""Build fail-closed zoning checks for every classification returned by Lenexa GIS."""

from __future__ import annotations

import re
from typing import Any

from shared.analysis.rule_coverage import rule_implementation
from shared.analysis.rule_execution import execution_contract
from shared.tools.lenexa_permits import all_lenexa_applications


UDC_URL = "https://online.encodeplus.com/regs/lenexa-ks/doc-viewer.aspx"
GIS_URL = "https://experience.arcgis.com/experience/9b4c537bb4fb49398d9c7d4305399ae1/page/zoningFLU"
PLANNING_TYPES = [f"lenexa_{item['id']}" for item in all_lenexa_applications() if item["category"] == "Planning and Land Use"]


# ArcGIS omits punctuation used by the UDC. Normalize both forms before lookup.
GIS_DISTRICT_ALIASES = {
    "RPE": "RP-E", "R1": "R-1", "RP1": "RP-1", "RP2": "RP-2", "RP3": "RP-3",
    "RP4": "RP-4", "RP5": "RP-5", "NPO": "NP-O", "CPO": "CP-O", "CP1": "CP-1",
    "CP2": "CP-2", "CP3": "CP-3", "CP4": "CP-4", "BP1": "BP-1", "BP2": "BP-2",
    "BPS": "BP-S",
}


# Section 4-1-B-26 schedules. District sections and approved development plans
# prevail when they impose a different value, so planned districts also receive
# controlling-record checks below.
DISTRICT_STANDARDS: dict[str, tuple[str, list[tuple[str, str, str]]]] = {
    "AG": ("4-1-B-4 and 4-1-B-26", [
        ("lot", "AG lot area and width", "Minimum lot area is 20 acres and minimum lot width is 300 feet."),
        ("density", "AG maximum density", "Maximum residential density is one dwelling unit per 20 acres."),
        ("setbacks", "AG minimum setbacks", "Minimum street, rear, and other setbacks are 50 feet."),
        ("height", "AG maximum height", "Maximum height is 35 feet for residential structures and 50 feet for agricultural structures."),
        ("open-space", "AG minimum open space", "At least 90 percent of the lot must remain open space."),
    ]),
    "RE": ("4-1-B-5 and 4-1-B-26", [
        ("lot", "RE lot area and width", "Minimum lot area is 43,560 square feet and minimum lot width is 200 feet."),
        ("density", "RE maximum density", "Maximum density is 1.0 dwelling unit per acre."),
        ("setbacks", "RE minimum setbacks", "Minimum street setback is 50 feet on perimeter streets and 35 feet on internal streets; minimum rear and other setbacks are 25 feet."),
        ("height", "RE maximum height", "Maximum building height is 35 feet."),
        ("open-space", "RE minimum open space", "At least 75 percent of the lot must remain open space."),
    ]),
    "RP-E": ("4-1-B-5 and 4-1-B-26", [
        ("lot", "RP-E lot area and width", "Minimum lot area is 43,560 square feet and minimum lot width is 200 feet unless the approved plan lawfully modifies the standard."),
        ("density", "RP-E maximum density", "Maximum density is 1.0 dwelling unit per acre unless the approved plan lawfully modifies the standard."),
        ("setbacks", "RP-E minimum setbacks", "Minimum street setback is 50 feet on perimeter streets and 35 feet on internal streets; minimum rear and other setbacks are 25 feet, subject to the approved plan."),
        ("height", "RP-E maximum height", "Maximum building height is 35 feet unless the approved plan lawfully modifies the standard."),
        ("open-space", "RP-E minimum open space", "At least 75 percent of the lot must remain open space unless the approved plan lawfully modifies the standard."),
    ]),
    "R-1": ("4-1-B-6 and 4-1-B-26", [
        ("lot", "R-1 lot area and width", "Minimum lot area is 8,000 square feet; minimum lot width is 70 feet, or 80 feet for a corner lot."),
        ("density", "R-1 maximum density", "Maximum density is 3.5 dwelling units per acre."),
        ("setbacks", "R-1 minimum setbacks", "Minimum street setback is 30 feet, including 20 feet from a side street; minimum rear setback is 20 feet and minimum other setback is 7 feet."),
        ("height", "R-1 maximum height", "Maximum building height is 35 feet."),
        ("open-space", "R-1 minimum open space", "At least 60 percent of the lot must remain open space."),
    ]),
    "RP-1": ("4-1-B-6 and 4-1-B-26", [
        ("lot", "RP-1 lot area and width", "Minimum lot area is 8,000 square feet; minimum lot width is 70 feet, or 80 feet for a corner lot, subject to the approved plan."),
        ("density", "RP-1 maximum density", "Maximum density is 3.5 dwelling units per acre unless the approved plan lawfully modifies the standard."),
        ("setbacks", "RP-1 minimum setbacks", "Minimum street setback is 30 feet, including 20 feet from a side street; minimum rear setback is 20 feet and minimum other setback is 7 feet, subject to the approved plan."),
        ("height", "RP-1 maximum height", "Maximum building height is 35 feet unless the approved plan lawfully modifies the standard."),
        ("open-space", "RP-1 minimum open space", "At least 60 percent of the lot must remain open space unless the approved plan lawfully modifies the standard."),
    ]),
    "RP-2": ("4-1-B-7 and 4-1-B-26", [
        ("lot", "RP-2 lot area and width", "Minimum lot area is 8,000 square feet excluding multifamily; minimum site area is 5,000 square feet per dwelling unit and minimum non-multifamily lot width is 80 feet, subject to the approved plan."),
        ("density", "RP-2 maximum density", "Maximum density is 8.0 dwelling units per acre unless the approved plan lawfully modifies the standard."),
        ("setbacks", "RP-2 minimum setbacks", "Minimum street, rear, and other setbacks are 25, 20, and 7 feet respectively, subject to the approved plan."),
        ("height", "RP-2 maximum height", "Maximum building height is 35 feet unless the approved plan lawfully modifies the standard."),
        ("open-space", "RP-2 minimum open space", "At least 60 percent of the lot must remain open space unless the approved plan lawfully modifies the standard."),
    ]),
    "RP-3": ("4-1-B-8 and 4-1-B-26", [
        ("lot", "RP-3 minimum site area", "Provide at least 3,630 square feet of site area per dwelling unit unless the approved plan lawfully modifies the standard."),
        ("density", "RP-3 maximum density", "Maximum density is 12.0 dwelling units per acre unless the approved plan lawfully modifies the standard."),
        ("setbacks", "RP-3 minimum setbacks", "Minimum street, rear, and other setbacks are 25, 20, and 7 feet respectively, subject to the approved plan."),
        ("height", "RP-3 maximum height", "Maximum building height is 35 feet unless the approved plan lawfully modifies the standard."),
        ("open-space", "RP-3 minimum open space", "At least 60 percent of the lot must remain open space unless the approved plan lawfully modifies the standard."),
    ]),
    "RP-4": ("4-1-B-9 and 4-1-B-26", [
        ("lot", "RP-4 minimum site area", "Provide at least 2,723 square feet of site area per dwelling unit unless the approved plan lawfully modifies the standard."),
        ("density", "RP-4 maximum density", "Maximum density is 16.0 dwelling units per acre unless the approved plan lawfully modifies the standard."),
        ("setbacks", "RP-4 minimum setbacks", "Minimum street, rear, and other setbacks are 20, 20, and 7 feet respectively, subject to the approved plan."),
        ("height", "RP-4 maximum height", "Maximum building height is 35 feet unless the approved plan lawfully modifies the standard."),
        ("open-space", "RP-4 minimum open space", "At least 60 percent of the lot must remain open space unless the approved plan lawfully modifies the standard."),
    ]),
    "RP-5": ("4-1-B-10 and 4-1-B-26", [
        ("lot", "RP-5 minimum site area", "Provide at least 1,210 square feet of site area per dwelling unit unless the approved plan lawfully modifies the standard."),
        ("density", "RP-5 maximum density", "Maximum density is 36.0 dwelling units per acre; more than 36 units per acre requires a Special Use Permit."),
        ("setbacks", "RP-5 minimum setbacks", "Minimum street, rear, and other setbacks are 30, 20, and 7 feet respectively, subject to the approved plan."),
        ("height", "RP-5 maximum height", "Maximum building height is 48 feet unless the approved plan or Special Use Permit lawfully modifies the standard."),
        ("open-space", "RP-5 minimum open space", "At least 40 percent of the lot must remain open space unless the approved plan lawfully modifies the standard."),
    ]),
    "NP-O": ("4-1-B-11 and 4-1-B-26", [
        ("district-size", "NP-O district size", "District area must be between 16,000 square feet and 10 acres."),
        ("setbacks", "NP-O minimum setbacks", "Minimum street setback is 30 feet and minimum other setback is 15 feet."),
        ("height", "NP-O maximum height", "Maximum building height is 35 feet."),
        ("open-space", "NP-O minimum open space", "At least 35 percent of the lot must remain open space."),
    ]),
    "CP-O": ("4-1-B-12 and 4-1-B-26", [
        ("district-size", "CP-O minimum district size", "Minimum district area is 40,000 square feet."),
        ("setbacks", "CP-O minimum setbacks", "Minimum street and other setbacks are 30 feet."),
        ("height", "CP-O height control", "The schedule sets no general maximum; apply the approved plan, airport, building-code, and adjacency limits."),
        ("open-space", "CP-O minimum open space", "At least 35 percent of the lot must remain open space."),
    ]),
    "CP-1": ("4-1-B-13 and 4-1-B-26", [
        ("district-size", "CP-1 district size", "District area must be between 3 and 10 acres."),
        ("setbacks", "CP-1 minimum setbacks", "Minimum street and other setbacks are 30 feet."),
        ("height", "CP-1 maximum height", "Maximum building height is 35 feet."),
        ("open-space", "CP-1 minimum open space", "At least 25 percent of the lot must remain open space."),
    ]),
    "CP-2": ("4-1-B-14 and 4-1-B-26", [
        ("district-size", "CP-2 district size", "District area must be between 10 and 30 acres."),
        ("setbacks", "CP-2 minimum setbacks", "Minimum street and other setbacks are 30 feet."),
        ("height", "CP-2 maximum height", "Maximum building height is 45 feet, or 65 feet for office buildings, unless the approved plan lawfully modifies the standard."),
        ("open-space", "CP-2 minimum open space", "At least 25 percent of the lot must remain open space."),
    ]),
    "CP-3": ("4-1-B-15 and 4-1-B-26", [
        ("district-size", "CP-3 district size", "District area must be between 30 and 100 acres."),
        ("setbacks", "CP-3 minimum setbacks", "Minimum street and other setbacks are 50 feet."),
        ("height", "CP-3 maximum height", "Maximum building height is 100 feet unless the approved plan lawfully modifies the standard."),
        ("open-space", "CP-3 minimum open space", "At least 25 percent of the lot must remain open space."),
    ]),
    "CP-4": ("4-1-B-16 and 4-1-B-26", [
        ("district-size", "CP-4 minimum district size", "Minimum district area is 1 acre."),
        ("setbacks", "CP-4 minimum setbacks", "Minimum street and other setbacks are 50 feet."),
        ("height", "CP-4 maximum height", "Maximum building height is 35 feet unless the approved plan lawfully modifies the standard."),
        ("open-space", "CP-4 minimum open space", "At least 25 percent of the lot must remain open space."),
    ]),
    "HBD": ("4-1-B-17 and 4-1-B-26", [
        ("setbacks", "HBD minimum setbacks", "Minimum street and other setbacks are 10 feet unless the approved plan lawfully modifies the standard."),
        ("height", "HBD maximum height", "Maximum building height is 45 feet unless the approved plan lawfully modifies the standard."),
        ("historic-design", "HBD historic design compatibility", "Verify the proposal against the HBD district purpose, approved plan, and applicable historic design conditions."),
    ]),
    "BP-1": ("4-1-B-18 and 4-1-B-26", [
        ("district-size", "BP-1 minimum district size", "Minimum district area is 10 acres."),
        ("setbacks", "BP-1 minimum setbacks", "Minimum street setback is 50 feet and minimum other setback is 30 feet."),
        ("height", "BP-1 maximum height", "Maximum building height is 45 feet, or 65 feet for office buildings, unless the approved plan lawfully modifies the standard."),
        ("open-space", "BP-1 minimum open space", "At least 25 percent of the lot must remain open space."),
    ]),
    "BP-2": ("4-1-B-19 and 4-1-B-26", [
        ("setbacks", "BP-2 minimum setbacks", "Minimum street setback is 50 feet and minimum other setback is 30 feet."),
        ("height", "BP-2 maximum height", "Maximum building height is 45 feet unless the approved plan lawfully modifies the standard."),
        ("open-space", "BP-2 minimum open space", "At least 25 percent of the lot must remain open space."),
    ]),
    "CC": ("4-1-B-28", [
        ("district-size", "CC project size", "A freestanding CC project should contain at least 20 acres; a smaller project must complement and extend a larger CC project and established urban edge."),
        ("blocks", "CC maximum block length", "Block length should not exceed 400 feet unless the approved development plan or development agreement provides otherwise."),
        ("setbacks", "CC setback and build-to ranges", "Unless the approved plan or development agreement provides otherwise, use 0 to 15 feet on mixed-use streets and 5 to 20 feet on residential streets."),
        ("height", "CC building height ranges", "Unless the approved plan or development agreement provides otherwise: residential 20-100 feet, retail 25-45 feet, and mixed-use or all other buildings 35-110 feet."),
        ("parking-study", "CC parking demand study", "Require a parking demand study at preliminary plan unless the Community Development Director approves otherwise."),
        ("sign-scheme", "CC project sign scheme", "Require a coordinated project signage scheme at final plan, including future sign locations and sizes."),
    ]),
    "PMU": ("4-1-B-29", [
        ("district-size", "PMU district size", "District area must be between 10 and 30 acres unless an approved action lawfully provides otherwise."),
        ("height", "PMU building height ranges", "Unless the approved plan or development agreement provides otherwise: residential 20-45 feet, retail 25-45 feet, mixed-use or all others 30-75 feet, and parking structures 15-45 feet."),
        ("parking-study", "PMU parking demand study", "Require a qualified parking demand study using the current ULI shared-parking model or another Director-approved model unless the Director approves otherwise."),
        ("open-space", "PMU public open space", "Provide usable public open space equal to at least 2 percent of total building square footage."),
        ("blocks", "PMU maximum block length", "Block length should not exceed 400 feet unless the approved development plan or development agreement provides otherwise."),
    ]),
}

PLAN_CONTROLLED_DISTRICTS = {
    "RP-E", "RP-1", "RP-2", "RP-3", "RP-4", "RP-5", "NP-O", "CP-O", "CP-1",
    "CP-2", "CP-3", "CP-4", "HBD", "BP-1", "BP-2", "BP-S", "CC", "PUD", "PMU",
}


def normalize_lenexa_district(value: str | None) -> str:
    raw = str(value or "").strip().upper()
    return GIS_DISTRICT_ALIASES.get(raw, raw)


def _rule(
    district: str,
    key: str,
    title: str,
    condition: str,
    check_type: str = "value_match",
    requires_values: bool = False,
    source_id: str = "udc",
    source_title: str = "Lenexa Unified Development Code",
    source_url: str = UDC_URL,
) -> dict[str, Any]:
    rule = {
        "id": f"lenexa-zoning-{re.sub(r'[^a-z0-9]+', '-', district.casefold()).strip('-')}-{key}",
        "category": "zoning", "group": f"{district} zoning standards", "rule": title,
        "condition": condition, "severity": "blocker", "source": source_title,
        "sourceIds": [source_id], "sourceLinks": [{"id": source_id, "title": source_title, "url": source_url}],
        "checkType": check_type, "verifiedAt": "2026-07-23", "permitTypes": PLANNING_TYPES,
        "ruleFamilyIds": [], "requiresContextStandard": requires_values, "requiresResolvedStandardValues": requires_values,
        "execution": execution_contract(check_type),
    }
    if requires_values:
        rule["execution"] = {**rule["execution"], "requiresContextStandard": True}
    return {**rule, "implementation": rule_implementation(rule)}


def _base_rules(district: str) -> list[dict[str, Any]]:
    return [
        _rule(district, "use", "Permitted or specially approved use", f"Compare every proposed use with the permitted, accessory, temporary, and special-use provisions for {district}; require the applicable Special Use Permit or approved-plan authorization when the use is not permitted by right."),
        _rule(district, "parking", "Parking and loading", "Calculate vehicle, accessible, bicycle, stacking, and loading requirements under Article 4-1-D and compare them with the plans and any approved reduction or shared-parking study."),
        _rule(district, "landscape", "Landscaping, buffering, screening, and lighting", "Verify the landscape plan, street trees, buffers, screening, refuse enclosure, exterior lighting, and parking-lot landscaping under Articles 4-1-C and 4-1-D."),
        _rule(district, "access", "Access, circulation, and public facilities", "Verify access, circulation, sidewalks, streets, easements, drainage, water, wastewater, fire flow, and other adequate-public-facility requirements under Article 4-1-C."),
        _rule(district, "design", "Architectural and site design standards", "Verify every applicable Article 4-1-C design, performance, outdoor-storage, compatibility, and adopted area-specific design standard."),
        _rule(district, "sign", "Sign standards", "Verify each sign's type, area, height, location, illumination, duration, and permit status under Article 4-1-E and any approved sign scheme."),
        _rule(district, "cross", "Zoning values agree across documents", "Verify district, use, dimensions, parking, and approved-plan values agree across the survey, site plan, civil plans, code analysis, and architectural set.", "cross_document"),
    ]


def _approved_plan_rules(district: str) -> list[dict[str, Any]]:
    return [
        _rule(district, "approved-plan-presence", "Approved development plan and conditions", "Locate the binding approved preliminary and final development plans, development agreement, ordinance, deviations, amendments, and conditions. Missing controlling records remain not verified.", "document_presence"),
        _rule(district, "approved-plan-values", "Approved-plan controlling values", "Extract all project-specific use, density, height, setback, parking, loading, open-space, landscaping, access, phasing, infrastructure, architecture, and signage controls from the approved records before evaluating the proposal.", "value_match", True),
        _rule(district, "approved-plan-match", "Proposal matches approved plan", "Compare the current proposal with every controlling approved-plan value and condition. A material deviation requires the applicable amendment or new approval.", "cross_document", True),
    ]


def build_lenexa_rules(classification: str | None, zoning_profile: dict[str, Any] | None = None, project_type: str | None = None) -> list[dict[str, Any]]:
    del project_type
    district = normalize_lenexa_district(classification)
    if not district:
        return []

    profile = zoning_profile or {}
    attributes = profile.get("attributes") or {}
    rules = [
        _rule(district, "gis", "Official zoning classification", "Verify the address and parcel against Lenexa's official zoning GIS, including district, subzone, ordinance, rezoning record, and district link.", "applicability", source_id="zoning_gis", source_title="City of Lenexa Zoning and Future Land Use GIS", source_url=GIS_URL),
        *_base_rules(district),
    ]

    catalog = DISTRICT_STANDARDS.get(district)
    if catalog:
        section, standards = catalog
        rules.extend(
            _rule(district, key, title, f"Under Lenexa UDC {section}: {condition}")
            for key, title, condition in standards
        )
    elif district not in {"BP-S", "PUD"}:
        rules.append(_rule(district, "unmapped", "Unmapped district standards", "The detected GIS district is not in the audited UDC district table. Do not pass zoning review until Planning confirms the classification and all controlling standards.", "applicability", True))

    if district in PLAN_CONTROLLED_DISTRICTS:
        rules.extend(_approved_plan_rules(district))

    subzone = str(attributes.get("SUBZONE") or "").strip()
    ordinance = str(attributes.get("ORDINANCE") or "").strip()
    rezoning = str(attributes.get("RZ") or "").strip()
    if subzone:
        rules.append(_rule(district, "subzone", "GIS subzone control", f"Apply the detected GIS subzone {subzone} and every subzone-specific standard or condition.", "applicability"))
    if ordinance or rezoning:
        label = ", ".join(part for part in [f"ordinance {ordinance}" if ordinance else "", f"rezoning {rezoning}" if rezoning else ""] if part)
        rules.append(_rule(district, "parcel-record", "Parcel-specific zoning action", f"Retrieve and apply the parcel-specific {label}, including all stipulations, approved plans, deviations, and amendments. Missing records remain not verified.", "document_presence"))

    return list({rule["id"]: rule for rule in rules}.values())


def has_lenexa_rule_coverage(classification: str | None) -> bool:
    district = normalize_lenexa_district(classification)
    return district in DISTRICT_STANDARDS or district in {"BP-S", "PUD"}
