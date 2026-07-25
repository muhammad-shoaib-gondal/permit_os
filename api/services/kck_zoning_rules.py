"""Build fail-closed zoning checks for every classification returned by KCK GIS."""

from __future__ import annotations

import re
from typing import Any

from shared.analysis.rule_coverage import rule_implementation
from shared.analysis.rule_execution import execution_contract
from shared.tools.kck_permits import all_kck_applications


CHAPTER_27_URL = "https://online.encodeplus.com/regs/kansascity-ks/doc-viewer.aspx?secid=122"
ZONING_GIS_URL = "https://gisweb.wycokck.org/arcgis/rest/services/GISPUB/Kansas_City_Ks_Zoning/FeatureServer/0"
DEVELOPMENT_APPLICATION_URL = "https://www.wycokck.org/files/assets/public/v/1/planning-amp-urban-design/documents/applications/2025-applications/wycokck-development-application_2025.pdf"
PIPER_ANNEX_URL = "https://www.wycokck.org/files/assets/public/v/1/planning-amp-urban-design/documents/piper-annex-1992.pdf"


# Chapter 27 section 27-434 makes each planned district subject to its
# equivalent base district, with the approved development plan controlling
# approved deviations and conditions.
CITY_PLANNED_EQUIVALENTS = {
    "RP-1": "R-1",
    "RP-1(B)": "R-1(B)",
    "RP-2": "R-2",
    "RP-2(B)": "R-2(B)",
    "RP-3": "R-3",
    "RP-4": "R-4",
    "RP-5": "R-5",
    "RP-6": "R-6",
    "RP-M": "R-M",
    "CP-0": "C-0",
    "CP-1": "C-1",
    "CP-D": "C-D",
    "CP-2": "C-2",
    "CP-3": "C-3",
    "MP-1": "M-1",
    "MP-2": "M-2",
    "MP-3": "M-3",
}


# Each tuple is key, user-facing title, and the controlling test. These are
# stored values from Chapter 27, not values inferred by the LLM.
CITY_DISTRICT_STANDARDS: dict[str, tuple[str, list[tuple[str, str, str]]]] = {
    "AG": ("27-452", [
        ("height", "AG maximum height", "Maximum principal-building height is two and one-half stories or 35 feet."),
        ("setbacks", "AG minimum yards", "Minimum front, interior-side, corner-side, and rear yards are 50, 20, 50, and 50 feet respectively."),
        ("lot", "AG lot dimensions", "Minimum lot width is 250 feet and minimum area is five acres per dwelling unit, subject to the section's lawful legacy-lot exceptions."),
        ("floor-area", "AG dwelling floor area", "Minimum dwelling floor area is 864 square feet."),
        ("parking", "AG dwelling parking", "Provide at least two off-street spaces per dwelling unit."),
    ]),
    "R": ("27-453", [
        ("height", "R maximum height", "Maximum principal-building height is two and one-half stories or 35 feet."),
        ("setbacks", "R minimum yards", "Minimum front, interior-side, corner-side, and rear yards are 50, 20, 50, and 50 feet respectively."),
        ("lot", "R lot dimensions", "Minimum lot width is 120 feet and minimum lot area is one acre."),
        ("floor-area", "R dwelling floor area", "Minimum dwelling floor area is 864 square feet."),
        ("parking", "R dwelling parking", "Provide at least two off-street spaces per dwelling unit."),
    ]),
    "R-1": ("27-454", [
        ("height", "R-1 maximum height", "Maximum principal-building height is two and one-half stories or 35 feet."),
        ("setbacks", "R-1 minimum yards", "Minimum front, interior-side, corner-side, and rear yards are 25, 7, 25, and 30 feet respectively, subject to the section's lawful narrow-lot exceptions."),
        ("lot", "R-1 lot dimensions", "Minimum width is 65 feet and minimum area is 7,150 square feet per dwelling unit, subject to lawful legacy-lot exceptions."),
        ("floor-area", "R-1 dwelling floor area", "Minimum dwelling floor area is 864 square feet."),
        ("parking", "R-1 dwelling parking", "Provide two spaces per dwelling unit, including at least one garage or carport space."),
    ]),
    "R-1(B)": ("27-455", [
        ("height", "R-1(B) maximum height", "Maximum principal-building height is two and one-half stories or 35 feet."),
        ("setbacks", "R-1(B) minimum yards", "Minimum front yard is 25 feet; interior side is ten percent of lot width with a three-foot minimum; corner-side and rear yards are 25 feet, subject to lawful exceptions."),
        ("lot", "R-1(B) lot dimensions", "Minimum width is 50 feet and minimum area is 5,000 square feet per dwelling unit, subject to lawful legacy-lot exceptions."),
        ("floor-area", "R-1(B) dwelling floor area", "Minimum dwelling floor area is 750 square feet."),
        ("parking", "R-1(B) dwelling parking", "Provide two off-street spaces per dwelling unit."),
    ]),
    "R-2": ("27-456", [
        ("height", "R-2 maximum height", "Maximum principal-building height is two and one-half stories or 35 feet."),
        ("setbacks", "R-2 minimum yards", "Minimum front, interior-side, corner-side, and rear yards are 25, 8, 25, and 30 feet respectively; apply the section's garage-front rule where triggered."),
        ("lot", "R-2 lot dimensions", "Minimum width is 75 feet and minimum lot area is 3,575 square feet per dwelling unit."),
        ("floor-area", "R-2 dwelling floor area", "Minimum floor area is 750 square feet per dwelling unit."),
        ("parking", "R-2 dwelling parking", "Provide two spaces per dwelling unit, including at least one garage or carport space."),
    ]),
    "R-2(B)": ("27-457", [
        ("height", "R-2(B) maximum height", "Maximum principal-building height is two and one-half stories or 35 feet."),
        ("setbacks", "R-2(B) minimum yards", "Minimum front, interior-side, corner-side, and rear yards are 25, 5, 20, and 25 feet respectively."),
        ("lot", "R-2(B) lot dimensions", "Minimum width is 50 feet and minimum lot area is 2,500 square feet per dwelling unit."),
        ("floor-area", "R-2(B) dwelling floor area", "Minimum floor area is 600 square feet per dwelling unit."),
        ("parking", "R-2(B) dwelling parking", "Provide at least one off-street space per dwelling unit."),
    ]),
    "R-3": ("27-458", [
        ("height", "R-3 maximum height", "Maximum principal-building height is two and one-half stories or 35 feet."),
        ("setbacks", "R-3 minimum yards", "Minimum front, interior-side, corner-side, and rear yards are 25, 10, 25, and 25 feet; paved parking is at least six feet from a property line except dwelling drives."),
        ("site-area", "R-3 project and unit area", "The project must contain at least one acre and at least 4,000 square feet of site area per dwelling unit."),
        ("floor-area", "R-3 dwelling floor area", "Minimum floor area is 750 square feet per dwelling unit."),
        ("parking", "R-3 dwelling parking", "Provide two spaces per dwelling unit, including at least one garage or carport space."),
        ("trees", "R-3 tree density", "Provide at least one tree per 4,500 square feet of site area."),
    ]),
    "R-4": ("27-459", [
        ("height", "R-4 maximum height", "Maximum height is two and one-half stories or 35 feet; qualifying senior housing may be up to three stories."),
        ("setbacks", "R-4 minimum yards", "Minimum front, interior-side, corner-side, and rear yards are 25, 10, 25, and 25 feet; paved parking is at least 25 feet from a street and six feet from other property lines."),
        ("density", "R-4 minimum site area", "Provide at least 3,000 square feet of site area per dwelling unit."),
        ("floor-area", "R-4 dwelling floor area", "Minimum floor area is 380 square feet per dwelling unit."),
        ("parking", "R-4 dwelling parking", "Provide 1.5 spaces for units with one or fewer bedrooms and two spaces for units with two or more bedrooms."),
        ("trees", "R-4 tree density", "Provide at least one tree per 4,500 square feet of site area."),
    ]),
    "R-5": ("27-460", [
        ("height", "R-5 maximum height", "Maximum building height is four stories."),
        ("setbacks", "R-5 minimum yards", "Minimum front, interior-side, corner-side, and rear yards are 25, 10, 25, and 25 feet; paved parking is at least 25 feet from a street and six feet from other property lines."),
        ("density", "R-5 site area and open space", "Provide at least 1,500 square feet of site area per dwelling unit and at least 40 percent nonvehicular open space."),
        ("floor-area", "R-5 dwelling floor area", "Minimum floor area is 380 square feet per dwelling unit."),
        ("parking", "R-5 dwelling parking", "Provide 1.5 spaces for units with one or fewer bedrooms and two spaces for units with two or more bedrooms."),
        ("trees", "R-5 tree density", "Provide at least one tree per 4,500 square feet of site area."),
    ]),
    "R-6": ("27-461", [
        ("height", "R-6 height", "Chapter 27 sets no general minimum or maximum building height in R-6; apply airport, approved-plan, and other applicable limits."),
        ("setbacks", "R-6 minimum yards", "Minimum front and corner-side yards are 25 feet; interior side is 10 feet plus three feet per story above four, capped at 25 feet; rear yard equals building height."),
        ("far", "R-6 floor area ratio", "Maximum floor area ratio is 3.0 and at least 40 percent of the site must remain nonvehicular open space."),
        ("floor-area", "R-6 dwelling floor area", "Minimum floor area is 380 square feet per dwelling unit."),
        ("parking", "R-6 dwelling parking", "Provide one space for units with one or fewer bedrooms and 1.5 spaces for units with two or more bedrooms, applying the section's senior-housing alternatives where eligible."),
        ("trees", "R-6 tree density", "Provide at least one tree per 4,500 square feet of site area."),
    ]),
    "R-M": ("27-462", [
        ("site", "R-M park density", "A mobile-home park must contain at least five acres and no more than seven mobile homes per acre."),
        ("height", "R-M maximum height", "Maximum mobile-home height is one story."),
        ("setbacks", "R-M minimum setbacks", "Park perimeter setback is 25 feet; space front is 25 feet; side is 20 feet on the entry side and five feet otherwise; corner-side is 25 feet; rear is 15 feet from a lot line and 25 feet from a street."),
        ("space", "R-M space dimensions", "Each mobile-home space must be at least 40 by 100 feet."),
        ("recreation", "R-M recreation and shelter", "Provide 200 square feet of recreation area per home with a 2,000-square-foot minimum, plus 12 square feet of storm-shelter area per lot."),
        ("parking", "R-M parking", "Provide two spaces per unit and, where streets are not public, visitor parking at 0.25 space per unit."),
    ]),
    "C-0": ("27-463", [
        ("height", "C-0 maximum height", "Maximum height is three stories or 40 feet; CP-0 may reach 12 stories subject to its approved plan."),
        ("setbacks", "C-0 minimum yards", "Minimum front, corner-side, and rear yards are 25 feet; interior side is 10 feet plus one foot per story above three; paved areas are at least six feet from property lines and 25 feet from streets."),
        ("parking", "C-0 parking", "Provide at least four spaces per 1,000 square feet of floor area unless the downtown exemption or an approved reduction applies."),
        ("landscape", "C-0 landscaping and screening", "Provide at least one tree per 7,000 square feet of site area and the required buffer adjoining single- or two-family residential zoning."),
    ]),
    "C-1": ("27-464", [
        ("height", "C-1 maximum height", "Maximum height is two stories or 35 feet."),
        ("setbacks", "C-1 minimum yards", "Minimum front and corner-side yards are 15 feet; side and rear yards are generally zero except where an abutting district or residential adjacency requires the stated setback."),
        ("parking", "C-1 parking", "Provide at least four spaces per 1,000 square feet of floor area unless an authorized reduction applies."),
        ("landscape", "C-1 landscaping and screening", "Provide at least one tree per 7,000 square feet and six-foot screening where required next to residential zoning."),
    ]),
    "C-D": ("27-465", [
        ("height", "C-D height", "Chapter 27 sets no general minimum or maximum height in C-D; apply airport, overlay, and approved-plan limits."),
        ("setbacks", "C-D setbacks", "No general setback is required except the applicable abutting-district setback."),
        ("parking", "C-D parking", "No general off-street parking is required except one space per dwelling unit and one per hotel room, which may be supplied on- or off-premises within 200 feet."),
        ("landscape", "C-D landscaping and screening", "Landscape available setback areas and provide six-foot screening where required next to residential zoning."),
    ]),
    "C-2": ("27-466", [
        ("height", "C-2 maximum height", "Maximum height is three stories; CP-2 may reach 12 stories subject to its approved plan."),
        ("setbacks", "C-2 minimum yards", "Minimum front and corner-side yards are 25 feet; side and rear yards are generally zero except for abutting-district controls; paved areas are at least six feet from property lines and ten feet from streets."),
        ("parking", "C-2 parking", "Provide at least four spaces per 1,000 square feet of floor area unless an authorized reduction applies."),
        ("landscape", "C-2 landscaping and screening", "Provide at least one tree per 7,000 square feet and six-foot screening where required next to residential zoning."),
    ]),
    "C-3": ("27-467", [
        ("height", "C-3 maximum height", "Maximum height is three stories; CP-3 may reach 12 stories subject to its approved plan."),
        ("setbacks", "C-3 minimum yards", "Minimum front and corner-side yards are 25 feet; side and rear yards follow applicable abutting-district controls; paved areas are at least six feet from property lines and ten feet from streets."),
        ("parking", "C-3 parking", "Provide at least four spaces per 1,000 square feet of floor area unless an authorized reduction applies."),
        ("landscape", "C-3 landscaping and screening", "Provide at least one tree per 7,000 square feet and six-foot screening where required next to residential zoning."),
    ]),
    "M-1": ("27-468", [
        ("height", "M-1 maximum height", "Maximum height is three stories or 50 feet; MP-1 may reach 150 feet subject to its approved plan."),
        ("setbacks", "M-1 minimum setbacks", "Buildings and structures are at least 25 feet from property lines; parking, loading, and paved areas are at least ten feet from property lines."),
        ("parking", "M-1 parking", "Provide at least one space per 500 square feet through 20,000 square feet and one per 1,000 square feet for the 20,000-to-50,000-square-foot increment; Planning determines the increment above 50,000 square feet."),
        ("landscape", "M-1 landscaping and screening", "Provide at least one tree per 10,000 square feet and six-foot architectural screening plus a buffer next to residential zoning."),
    ]),
    "M-2": ("27-469", [
        ("height", "M-2 height", "No general height limit applies, except an abutting district's height limit applies within 25 feet of the common property line."),
        ("setbacks", "M-2 minimum setbacks", "Buildings and structures are at least ten feet from property lines; parking, loading, display, and storage areas are at least six feet away; use 15 feet along side and rear lines next to residential zoning."),
        ("parking", "M-2 parking", "Apply the M-1 industrial parking formula; commercial uses provide parking at the C-3 rate."),
        ("landscape", "M-2 landscaping and screening", "Provide at least one tree per 10,000 square feet and six-foot architectural screening plus a buffer next to residential zoning."),
    ]),
    "M-3": ("27-470", [
        ("height", "M-3 height", "No general height limit applies except airport approach-zone controls and approved conditions."),
        ("plan-review", "M-3 development plan review", "For the heavy uses identified in section 27-470, require Planning Commission approval of the site, elevation, drainage, wastewater, screening, landscaping, and performance-standard plan before permit issuance."),
        ("setbacks", "M-3 setbacks", "Planning review determines project setbacks; provide at least 15 feet along side and rear property lines next to residential zoning."),
        ("parking", "M-3 parking", "Apply the M-1 industrial parking formula unless the approved plan establishes the controlling requirement."),
        ("landscape", "M-3 landscaping and screening", "Landscape all unpaved areas and provide six-foot screening plus a buffer next to residential zoning."),
    ]),
    "B-P": ("27-472", [
        ("site", "B-P minimum district area", "The planned business park must contain at least ten acres under unified control."),
        ("height", "B-P maximum height", "Buildings may not exceed 50 feet; nonbuilding structures may reach 100 feet when set back from the property line by at least their height."),
        ("setbacks", "B-P perimeter setbacks", "Next to residential property, building and paved-area setbacks are 50 and 25 feet; at the park perimeter they are 40 and ten feet; elsewhere they are 25 and six feet."),
        ("parking", "B-P parking", "Provide at least one space per 500 square feet through 20,000 square feet and one per 1,000 square feet for the 20,000-to-50,000-square-foot increment; Planning determines the increment above 50,000 square feet."),
        ("landscape", "B-P landscaping and screening", "Provide at least one tree per 8,000 square feet and six-foot architectural screening with a 25-foot buffer next to residential zoning."),
    ]),
}


LEGACY_PLANNED_EQUIVALENTS = {
    "RP-1A": "R-1A",
    "RP-5": "R-5",
    "CP-2": "C-2",
    "CP-3": "C-3",
}


LEGACY_DISTRICT_STANDARDS: dict[str, list[tuple[str, str, str]]] = {
    "AG": [
        ("height", "Wyco AG maximum height", "Maximum height is two and one-half stories or 35 feet."),
        ("setbacks", "Wyco AG minimum yards", "For dwellings, minimum front, side, and rear yards are 50, 30, and 50 feet; other permitted uses require 100-foot yards."),
        ("lot", "Wyco AG lot dimensions", "A dwelling lot requires 20 acres and 660 feet of frontage; other permitted uses require at least 80,000 square feet, subject to lawful lots of record."),
        ("floor-area", "Wyco AG dwelling floor area", "Minimum dwelling floor area is 1,250 square feet, or 1,000 square feet on qualifying pre-resolution plats."),
        ("parking", "Wyco AG dwelling parking", "Provide two spaces per dwelling unit plus two spaces for an accessory home occupation or principal agricultural use."),
    ],
    "R": [
        ("height", "Wyco R maximum height", "Maximum height is two and one-half stories or 35 feet."),
        ("setbacks", "Wyco R minimum yards", "Minimum front and corner-side yards are 50 feet; interior side is the greater of ten feet or ten percent of lot width, capped at 20 feet; rear is the greater of 30 feet or 20 percent of lot depth, capped at 45 feet."),
        ("lot", "Wyco R lot dimensions", "Minimum lot area is five acres and minimum frontage is 330 feet, subject to lawful lots of record."),
        ("floor-area", "Wyco R dwelling floor area", "Minimum dwelling floor area is 1,250 square feet."),
        ("utilities", "Wyco R wastewater", "An onsite septic system requires the applicable health-department construction approval."),
    ],
    "R-1": [
        ("height", "Wyco R-1 maximum height", "Maximum height is two and one-half stories or 35 feet."),
        ("setbacks", "Wyco R-1 minimum yards", "Minimum front yard is 50 feet, interior side is 20 feet, corner-side is 30 feet, and rear is the greater of 30 feet or 20 percent of lot depth, capped at 45 feet."),
        ("lot", "Wyco R-1 lot dimensions", "Minimum lot area is one acre and minimum frontage is 150 feet, subject to lawful lots of record."),
        ("floor-area", "Wyco R-1 dwelling floor area", "Minimum dwelling floor area is 1,250 square feet."),
        ("utilities", "Wyco R-1 utilities", "A state-approved public water system is required; an onsite septic system requires the applicable health-department construction approval."),
    ],
    "R-1A": [
        ("height", "Wyco R-1A maximum height", "Maximum height is two and one-half stories or 35 feet."),
        ("setbacks", "Wyco R-1A minimum yards", "Minimum front yard is 35 feet; interior side is the greater of seven feet or ten percent of lot width, capped at ten feet; corner-side is 20 feet; rear follows the R-1 legacy standard."),
        ("lot", "Wyco R-1A lot dimensions", "Minimum lot area is 15,000 square feet and minimum frontage is 85 feet, subject to lawful lots of record."),
        ("floor-area", "Wyco R-1A dwelling floor area", "Minimum dwelling floor area is 1,250 square feet."),
        ("utilities", "Wyco R-1A utilities", "State-approved public water and public sewer systems are required."),
    ],
    "R-1B": [
        ("height", "Wyco R-1B maximum height", "Maximum height is two and one-half stories or 35 feet."),
        ("setbacks", "Wyco R-1B minimum yards", "Minimum front yard is 25 feet; interior side is the greater of seven feet or ten percent of lot width, capped at ten feet; corner-side is 20 feet; rear is 30 feet."),
        ("lot", "Wyco R-1B lot dimensions", "Minimum lot area is 8,000 square feet and minimum frontage is 70 feet, subject to lawful lots of record."),
        ("floor-area", "Wyco R-1B dwelling floor area", "Minimum dwelling floor area is 1,000 square feet."),
        ("utilities", "Wyco R-1B utilities", "Public water and public sewer systems are required."),
    ],
    "R-2": [
        ("height", "Wyco R-2 maximum height", "Maximum height is two and one-half stories or 35 feet."),
        ("setbacks", "Wyco R-2 minimum yards", "Minimum front yard is 35 feet; interior side is the greater of eight feet or ten percent of lot width, capped at ten feet; corner-side is 30 feet; rear follows the R-1 legacy standard."),
        ("lot", "Wyco R-2 lot dimensions", "Minimum lot area is 10,000 square feet and minimum frontage is 80 feet, subject to lawful lots of record."),
        ("floor-area", "Wyco R-2 dwelling floor area", "Minimum floor area is 750 square feet per dwelling unit."),
        ("parking", "Wyco R-2 dwelling parking", "Provide two off-street spaces per dwelling unit."),
    ],
    "R-5": [
        ("height", "Wyco R-5 maximum height", "Maximum townhouse height is 35 feet."),
        ("setbacks", "Wyco R-5 minimum yards", "Minimum front yard is 30 feet, end-group side yard is ten feet, between-group separation is 20 feet plus ten feet where a driveway intervenes, corner-side is 15 feet, and rear is 25 feet."),
        ("density", "Wyco R-5 unit area and open space", "Provide at least 3,500 square feet per unit plus common open space equal to the greater of the difference to 5,000 square feet per unit or 20 percent of gross land area."),
        ("floor-area", "Wyco R-5 townhouse floor area", "Each unit must contain at least 750 square feet and each townhouse group must average at least 900 square feet per unit."),
        ("parking", "Wyco R-5 parking", "Provide two spaces per townhouse within 150 feet of the served door."),
    ],
    "C-1": [
        ("height", "Wyco C-1 maximum height", "Maximum height is two stories or 35 feet."),
        ("setbacks", "Wyco C-1 minimum yards", "Apply the archived C-1 front, side, corner-side, and rear-yard standards, including the more restrictive adjoining-residential controls."),
        ("parking", "Wyco C-1 parking", "Provide four off-street spaces per 1,000 square feet of contributing floor area unless an authorized exception applies."),
        ("loading", "Wyco C-1 loading", "Provide and dimension off-street loading according to gross floor area, use, occupants, delivery frequency, and delivery-vehicle size."),
        ("screening", "Wyco C-1 residential screening", "Provide permanent five- to eight-foot screening along boundaries next to residential use."),
    ],
    "C-2": [
        ("height", "Wyco C-2 maximum height", "Maximum height is three stories or 45 feet; the planned counterpart may reach ten stories or 144 feet only under its approved plan."),
        ("setbacks", "Wyco C-2 minimum yards", "Minimum front yard is 30 feet; side yards follow adjacency controls; rear yard is 25 feet."),
        ("density", "Wyco C-2 residential lot area", "Where dwelling uses are lawful, provide at least 7,500 square feet for one family, 5,000 square feet per two-family unit, or 3,500 square feet per multifamily unit."),
        ("parking", "Wyco C-2 parking", "Provide four off-street spaces per 1,000 square feet of contributing floor area unless an authorized exception applies."),
        ("loading", "Wyco C-2 loading", "For buildings over 5,000 square feet, provide one loading space per 50,000 square feet or fraction and required maneuvering area."),
        ("screening", "Wyco C-2 residential screening", "Provide permanent five- to eight-foot screening along residential boundaries and landscape all unpaved areas."),
    ],
    "C-3": [
        ("height", "Wyco C-3 maximum height", "Maximum height is three stories or 45 feet."),
        ("setbacks", "Wyco C-3 minimum yards", "Minimum front yard is 15 feet, subject to adjacency and narrow-lot exceptions; corner-side is 15 feet; side and rear yards follow the archived adjacency controls, with a 25-foot rear yard where triggered."),
        ("parking", "Wyco C-3 parking", "Provide four off-street spaces per 1,000 square feet of contributing floor area unless an authorized exception applies."),
        ("loading", "Wyco C-3 loading", "For buildings over 5,000 square feet, provide one loading space per 50,000 square feet or fraction and required maneuvering area."),
        ("screening", "Wyco C-3 residential screening", "Provide permanent five- to eight-foot screening along residential boundaries and landscape all unpaved areas."),
    ],
}

PLANNING_PERMIT_TYPES = ["planning_entitlement"] + [
    f"kck_{application['id']}"
    for application in all_kck_applications()
    if application["category"] == "Planning and Land Use"
]


def _rule(
    district: str,
    key: str,
    title: str,
    condition: str,
    *,
    source_id: str = "planning_code",
    source_title: str = "Unified Government Code of Ordinances Chapter 27",
    source_url: str = CHAPTER_27_URL,
    check_type: str = "value_match",
    severity: str = "blocker",
    requires_context: bool = True,
) -> dict[str, Any]:
    rule = {
        "id": f"kck-zoning-{re.sub(r'[^a-z0-9]+', '-', district.casefold()).strip('-')}-{key}",
        "category": "zoning",
        "group": f"{district} zoning standards",
        "rule": title,
        "condition": condition,
        "severity": severity,
        "source": source_title,
        "sourceIds": [source_id],
        "sourceLinks": [{"id": source_id, "title": source_title, "url": source_url}],
        "checkType": check_type,
        "verifiedAt": "2026-07-22",
        "permitTypes": PLANNING_PERMIT_TYPES,
        "ruleFamilyIds": [],
        "requiresContextStandard": requires_context and check_type == "value_match",
        "requiresResolvedStandardValues": requires_context and check_type == "value_match",
        "execution": execution_contract(check_type),
    }
    if rule["requiresContextStandard"]:
        rule["execution"] = {**rule["execution"], "requiresContextStandard": True}
    return {**rule, "implementation": rule_implementation(rule)}


def _base_rules(district: str, *, include_unresolved_values: bool) -> list[dict[str, Any]]:
    prefix = (
        f"Use the controlling Chapter 27 standards for {district}, resolved from the official district "
        "record. Missing controlling values produce not verified, never a user-supplied threshold or pass. "
    )
    rules = [
        _rule(district, "use", "Permitted or specially approved use", prefix + "Compare the proposed use with the district's permitted-use list and verify any required special use or development-plan approval."),
        _rule(district, "loading", "Loading and circulation", prefix + "Verify loading, drive aisles, stacking, access, and circulation against the use-specific Chapter 27 standards and approved plans."),
        _rule(district, "signs", "Sign standards", prefix + "Compare each proposed sign's type, area, height, placement, illumination, and spacing with the current sign code and any overlay controls."),
        _rule(district, "cross-document", "Zoning values agree across documents", "Verify that district, use, height, setbacks, parcel dimensions, area, parking, and approved-plan references agree across the survey, site plan, code analysis, civil plans, and architectural plans.", check_type="cross_document", requires_context=False),
    ]
    if include_unresolved_values:
        rules[1:1] = [
            _rule(district, "height", "Maximum building height", prefix + "Extract proposed building height from the architectural set and compare it with the controlling maximum and any approved exception."),
            _rule(district, "front-setback", "Front setback", prefix + "Compare the site-plan front setback with the controlling district, platted building line, and approved-plan requirement."),
            _rule(district, "side-setback", "Interior and street-side setbacks", prefix + "Compare every proposed side setback with the controlling district and adjacency-specific standards."),
            _rule(district, "rear-setback", "Rear setback", prefix + "Compare the proposed rear setback with the controlling district and adjacency-specific standards."),
            _rule(district, "lot", "Lot area and width", prefix + "Compare parcel area and width from the survey or official parcel record with the district minimums and lawful-lot exceptions."),
            _rule(district, "density", "Residential density or development intensity", prefix + "When applicable, calculate dwelling-unit density, lot area per unit, floor area ratio, and lot coverage from project documents and compare each with the controlling standard."),
            _rule(district, "parking", "Vehicle parking", prefix + "Calculate required, proposed, accessible, compact, and bicycle parking from the proposed uses and compare them with Chapter 27 parking standards and approved reductions."),
            _rule(district, "landscape", "Landscaping, buffering, screening, and lighting", prefix + "Verify landscape area, street trees, buffers, screening, refuse enclosures, and site lighting where triggered by the use or adjoining districts."),
        ]
    return rules


def _catalog_rules(district: str, base_district: str, *, planned: bool) -> list[dict[str, Any]]:
    section, standards = CITY_DISTRICT_STANDARDS[base_district]
    qualifier = (
        f" {district} uses {base_district} as its section 27-434 equivalent; the approved development plan "
        "controls any lawfully approved variation or additional condition."
        if planned
        else ""
    )
    source = f"Chapter 27 section {section}, {base_district} district standards"
    return [
        _rule(
            district,
            f"catalog-{key}",
            title.replace(base_district, district, 1) if planned else title,
            condition + qualifier,
            source_title=source,
            requires_context=False,
        )
        for key, title, condition in standards
    ]


def _legacy_catalog_rules(district: str, base_district: str, *, planned: bool) -> list[dict[str, Any]]:
    qualifier = (
        f" {district} is the planned counterpart of legacy {base_district}; its approved development plan "
        "controls permitted deviations and additional conditions."
        if planned
        else ""
    )
    return [
        _rule(
            district,
            f"legacy-catalog-{key}",
            title.replace(f"Wyco {base_district}", f"Wyco {district.replace(' (Wyco)', '')}", 1) if planned else title,
            condition + qualifier,
            source_id="piper_annex_zoning",
            source_title="Unified Government Piper Annex Zoning Code (legacy Wyandotte districts)",
            source_url=PIPER_ANNEX_URL,
            requires_context=False,
        )
        for key, title, condition in LEGACY_DISTRICT_STANDARDS[base_district]
    ]


def _approved_plan_rules(district: str, *, legacy: bool = False) -> list[dict[str, Any]]:
    source_kwargs = (
        {
            "source_id": "piper_annex_zoning",
            "source_title": "Unified Government Piper Annex Zoning Code (legacy Wyandotte districts)",
            "source_url": PIPER_ANNEX_URL,
        }
        if legacy
        else {}
    )
    return [
        _rule(
            district,
            "approved-preliminary-plan",
            "Approved preliminary development plan",
            "Locate the parcel's approved preliminary development plan and controlling ordinance. Extract its use, dimensional, access, landscape, phasing, and condition standards; absent records remain not verified.",
            check_type="document_presence",
            requires_context=False,
            **source_kwargs,
        ),
        _rule(
            district,
            "approved-final-plan",
            "Approved final development plan",
            "Compare the proposal against the current approved final development plan and every condition of approval. A material deviation requires the applicable plan amendment or new approval.",
            check_type="cross_document",
            requires_context=False,
            **source_kwargs,
        ),
    ]


def build_kck_rules(
    classification: str | None,
    zoning_profile: dict[str, Any] | None = None,
    project_type: str | None = None,
) -> list[dict[str, Any]]:
    del project_type
    value = str(classification or "").strip()
    if not value:
        return []
    profile = zoning_profile or {}
    attributes = profile.get("attributes") or {}
    components = [part.strip() for part in re.split(r"[/,]", value) if part.strip()]
    rules: list[dict[str, Any]] = []

    rules.append(
        _rule(
            value,
            "gis-record",
            "Official parcel zoning record",
            "Verify the project address and parcel location against the KCK zoning GIS response, including base district, zoning label, ordinance numbers, split-zone flag, historic flag, and environs flag.",
            source_id="zoning_gis",
            source_title="Unified Government Kansas City, Kansas Zoning GIS",
            source_url=ZONING_GIS_URL,
            check_type="applicability",
            requires_context=False,
        )
    )

    for component in components:
        is_legacy = "(WYCO)" in component.upper()
        normalized = component.upper().replace(" (WYCO)", "").strip()
        if is_legacy:
            base = LEGACY_PLANNED_EQUIVALENTS.get(normalized, normalized)
            has_catalog = base in LEGACY_DISTRICT_STANDARDS
            rules.extend(_base_rules(component, include_unresolved_values=not has_catalog))
            if has_catalog:
                rules.extend(
                    _legacy_catalog_rules(
                        component,
                        base,
                        planned=normalized in LEGACY_PLANNED_EQUIVALENTS,
                    )
                )
            if normalized in LEGACY_PLANNED_EQUIVALENTS:
                rules.extend(_approved_plan_rules(component, legacy=True))
            rules.append(
                _rule(
                    component,
                    "legacy-district",
                    "Legacy Wyandotte County district control",
                    "Apply the archived Wyandotte district standards and any parcel-specific ordinance or approved plan. Do not substitute the similarly named Kansas City district.",
                    source_id="piper_annex_zoning",
                    source_title="Unified Government Piper Annex Zoning Code (legacy Wyandotte districts)",
                    source_url=PIPER_ANNEX_URL,
                    check_type="applicability",
                    requires_context=False,
                )
            )
            continue

        base = CITY_PLANNED_EQUIVALENTS.get(normalized, normalized)
        has_catalog = base in CITY_DISTRICT_STANDARDS
        rules.extend(_base_rules(component, include_unresolved_values=not has_catalog))
        if has_catalog:
            rules.extend(
                _catalog_rules(
                    component,
                    base,
                    planned=normalized in CITY_PLANNED_EQUIVALENTS,
                )
            )
        if normalized in CITY_PLANNED_EQUIVALENTS or normalized == "B-P":
            rules.extend(_approved_plan_rules(component))
        if normalized == "TND":
            rules.extend(_approved_plan_rules(component))
            rules.append(
                _rule(
                    component,
                    "tnd-regulating-plan",
                    "TND regulating plan and transect standards",
                    "Identify the approved TND regulating plan and the parcel's transect or subdistrict, then apply its building placement, frontage, height, parking, open-space, and design standards. TND has no single citywide numeric table that can replace this plan.",
                    check_type="document_presence",
                    requires_context=False,
                )
            )

    split_value = str(attributes.get("SPLIT_ZONE") or "").strip().casefold()
    if len(components) > 1 or split_value not in {"", "0", "false", "n", "no"}:
        rules.append(
            _rule(value, "split-zone", "Split-zoning boundary", "Overlay the project limits on the official zoning polygons and apply each district's standards only to the work and parcel portion inside that district. Missing boundary evidence is not verified.", source_id="zoning_gis", source_title="Unified Government Kansas City, Kansas Zoning GIS", source_url=ZONING_GIS_URL, check_type="cross_document", requires_context=False)
        )

    historic = str(attributes.get("HISTORIC") or "").strip().casefold()
    environs = str(attributes.get("ENVIRONS") or "").strip().casefold()
    zoning_label = str(attributes.get("ZONING_LABEL") or "").upper()
    if historic not in {"", "0", "false", "n", "no"} or "-H" in zoning_label:
        rules.append(
            _rule(value, "historic", "Historic property approval", "Require Historic Preservation review and the applicable Certificate of Appropriateness before building or demolition approval; compare the work with the adopted historic standards and approval conditions.", source_id="development_application", source_title="UG Development Application and Historic Preservation Requirements", source_url=DEVELOPMENT_APPLICATION_URL, check_type="sequencing", requires_context=False)
        )
    if environs not in {"", "0", "false", "n", "no"} or "-E" in zoning_label:
        rules.append(
            _rule(value, "environs", "Historic environs review", "Require historic environs review when the parcel is within a designated landmark's environs and verify the proposal against the resulting approval or conditions.", source_id="development_application", source_title="UG Development Application and Historic Preservation Requirements", source_url=DEVELOPMENT_APPLICATION_URL, check_type="sequencing", requires_context=False)
        )

    deduplicated = {rule["id"]: rule for rule in rules}
    return list(deduplicated.values())


def has_kck_rule_coverage(classification: str | None) -> bool:
    return bool(build_kck_rules(classification))
