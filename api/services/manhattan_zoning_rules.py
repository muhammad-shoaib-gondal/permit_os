"""Build review rules for every zoning district returned by Manhattan GIS."""

from __future__ import annotations

from typing import Any


RESIDENTIAL_SOURCE = "MDC section 26-2C-4, Tables 26-2C-4.1 through 26-2C-4.5"
NONRES_LOT_SOURCE = "MDC section 26-2D-2, Table 26-2D-2.1"
NONRES_BULK_SOURCE = "MDC section 26-2D-3, Table 26-2D-3.1"
GENERAL_NONRES_SOURCE = "MDC section 26-2D-1"

# label, minimum lot area, lot area per unit, minimum width, maximum height,
# maximum coverage, front, rear, interior side, street side
RESIDENTIAL_STANDARDS: dict[str, list[tuple[Any, ...]]] = {
    "RL": [
        ("detached house", 6000, None, "50 ft", 35, 20, 25, 35, "8 ft", 15),
        ("patio detached house", 4500, None, "40 ft", 35, 15, 20, 35, "10 ft exterior / 0 ft attached side", 10),
        ("2-5 unit attached residence", 1800, 1800, "18 ft per unit", 35, 20, 20, 35, "6 ft exterior / 0 ft attached side", 15),
        ("3-5 unit multiple-family residence", 7000, 2200, "50 ft", 35, 20, 20, 35, "8 ft", 15),
        ("permitted nonresidential use", 10000, None, "75 ft", 35, 20, 25, 35, "15 ft", 15),
    ],
    "RL-A": [
        ("detached house", 6000, None, "40 ft", 35, 15, 15, 45, "6 ft", 10),
        ("patio detached house", 4500, None, "40 ft", 35, 15, 15, 45, "6 ft exterior / 0 ft attached side", 10),
        ("2-18 unit attached residence", 1800, 1200, "18 ft per unit", 35, 15, 15, 40, "6 ft exterior / 0 ft attached side", 10),
        ("3-5 unit multiple-family residence", 7500, 1500, "50 ft", 35, 15, 15, 45, "6 ft", 10),
        ("6-17 unit multiple-family residence", 9000, 1500, "50 ft", 45, 15, 15, 45, "8 ft", 10),
        ("permitted nonresidential use", 10000, None, "75 ft", 35, 20, 25, 35, "15 ft", 15),
    ],
    "RM": [
        ("detached house", 6000, None, "40 ft", 35, 15, 15, 45, "6 ft", 10),
        ("patio detached house", 4500, None, "40 ft", 35, 15, 15, 45, "6 ft exterior / 0 ft attached side", 10),
        ("2-18 unit attached residence", 1800, 750, "18 ft per unit", 35, 15, 15, 40, "6 ft exterior / 0 ft attached side", 10),
        ("3-5 unit multiple-family residence", 7000, 1200, "50 ft", 35, 15, 15, 45, "5 ft", 10),
        ("6-17 unit multiple-family residence", 10000, 1200, "50 ft", 45, 15, 15, 45, "5 ft", 10),
        ("18+ unit multiple-family residence", 25000, 1200, "50 ft", 60, 15, 20, 50, "5 ft", 12),
        ("permitted nonresidential use", 10000, None, "75 ft", 35, 20, 25, 35, "15 ft", 15),
    ],
    "RH": [
        ("2-18 unit attached residence", 1800, 700, "18 ft per unit", 35, 15, 15, 40, "6 ft exterior / 0 ft attached side", 10),
        ("3-5 unit multiple-family residence", 5500, 680, "50 ft", 35, 15, 15, 45, "5 ft", 10),
        ("6-17 unit multiple-family residence", 6000, 680, "50 ft", 45, 15, 15, 45, "5 ft", 10),
        ("18+ unit multiple-family residence", 15000, 680, "50 ft", 60, 15, 20, 50, "5 ft", 12),
        ("permitted nonresidential use", 10000, None, "75 ft", 35, 20, 25, 60, "15 ft", 15),
    ],
    "RC": [
        ("2-18 unit attached residence", 1800, 1800, "18 ft per unit", 35, 15, 15, 40, "6 ft exterior / 0 ft attached side", 10),
        ("3-5 unit multiple-family residence", 7000, 500, "50 ft", 35, 15, 15, 50, "5 ft", 10),
        ("6-17 unit multiple-family residence", 8500, 500, "50 ft", 45, 15, 15, 60, "5 ft", 10),
        ("18+ unit multiple-family residence", 17500, 500, "100 ft", 60, 15, 20, 100, "5 ft", 12),
        ("mid-rise residence", 15000, 500, "100 ft", 85, 5, 0, 100, "0 ft", 5),
        ("permitted nonresidential use", 10000, None, "75 ft", 35, 20, 25, 60, "15 ft", 15),
    ],
}

# lot area in thousands of square feet, width, landscape surface ratio, density
NONRES_LOT_STANDARDS = {
    "BC": (7.5, 50, 20, 50), "CN": (15, 75, 18, 24), "CC": (20, 100, 15, 12),
    "BP": (25, 100, 20, 30), "CA": (None, None, None, None), "CD": (None, None, None, None),
    "MX": (30, None, 10, None), "ICS": (10, 75, 15, 12), "IL": (10, 80, 20, 12),
    "IG": (10, 75, 15, 0), "UC": (None, None, None, None),
    "PI-1": (43.5, 125, 20, 0), "PI-2": (43.5, 125, 20, 0),
}

# establishment area, height, coverage, front, rear, side, street side,
# separation from residential district, parking front, parking street side
NONRES_BULK_STANDARDS = {
    "BC": (25, 45, 50, 15, 15, 8, 15, 15, 10, 10),
    "CN": (35, 40, 50, 15, None, None, 15, 8, 10, 10),
    "CC": (None, 40, 50, 25, None, None, 20, 35, 15, 10),
    "BP": (None, 75, 35, 50, 25, 35, 50, 75, 35, 35),
    "CA": (25, None, None, None, None, None, None, None, None, None),
    "CD": (None, None, None, None, None, None, None, 8, None, None),
    "MX": (None, 75, 90, None, None, None, None, 15, None, None),
    "ICS": (None, 50, 50, 25, None, None, 20, 10, 10, 10),
    "IL": (None, 75, 40, 25, 25, 20, 25, 35, 20, 20),
    "IG": (None, None, 40, 35, 25, 15, 35, 35, 15, 10),
    "UC": (None, None, None, 50, 50, 50, 50, 50, 25, 25),
    "PI-1": (None, 50, 50, 25, 25, 10, 25, 25, 15, 10),
    "PI-2": (None, 50, 50, 25, 25, 10, 25, 25, 15, 10),
}

DISTRICTS = set(RESIDENTIAL_STANDARDS) | set(NONRES_LOT_STANDARDS) | {"LR", "PUD"}


def _rule(district: str, key: str, title: str, condition: str, source: str, severity: str = "major") -> dict[str, Any]:
    return {
        "id": f"manhattan-{district.lower()}-{key}",
        "category": "zoning",
        "group": f"{district} zoning standards",
        "rule": title,
        "condition": condition,
        "severity": severity,
        "source": source,
    }


def _residential_rules(district: str) -> list[dict[str, Any]]:
    rules = []
    for index, standard in enumerate(RESIDENTIAL_STANDARDS[district]):
        label, lot, per_unit, width, height, coverage, front, rear, side, street = standard
        density = f" and at least {per_unit:,} sq ft per dwelling unit" if per_unit else ""
        condition = (
            f"{label.title()}: lot >= {lot:,} sq ft{density}; width >= {width}; height <= {height} ft; "
            f"coverage <= {coverage}%; setbacks (front/rear/interior/street) >= "
            f"{front}/{rear}/{side}/{street}."
        )
        rules.append(_rule(district, f"housing-{index + 1}", f"{label.title()} dimensional envelope", condition, RESIDENTIAL_SOURCE, "critical"))
    rules.extend([
        _rule(district, "garage", "Garage driveway setback", "A garage and the portion of a residential building containing it must be at least 20 ft from the front or street-side property line serving its driveway, even where the district table allows a smaller setback.", "MDC section 26-2C-4"),
        _rule(district, "development-type", "Residential development type adjustments", "Determine the mapped development type from city GIS and project approvals. Cluster and master-planned development may reduce minimum lot area and width by 20%, reduce front and side setbacks by 25%, and increase building coverage to 50%; do not apply those adjustments to standard development.", RESIDENTIAL_SOURCE),
    ])
    return rules


def _nonres_rules(district: str) -> list[dict[str, Any]]:
    lot, width, landscape, density = NONRES_LOT_STANDARDS[district]
    establishment, height, coverage, front, rear, side, street, residential, parking_front, parking_street = NONRES_BULK_STANDARDS[district]
    rules: list[dict[str, Any]] = []
    if lot is not None:
        rules.append(_rule(district, "lot-area", "Minimum lot area", f"Lot area must be at least {lot * 1000:,.0f} sq ft.", NONRES_LOT_SOURCE))
    if width is not None:
        rules.append(_rule(district, "frontage", "Minimum street frontage", f"Lot width or street frontage must be at least {width} ft.", NONRES_LOT_SOURCE))
    if landscape is not None:
        rules.append(_rule(district, "landscape", "Minimum landscape surface ratio", f"At least {landscape}% of the lot must remain pervious as qualifying lawn, landscaping, screening, or buffering.", NONRES_LOT_SOURCE))
    if density is not None:
        condition = "Residential uses are not permitted by the base district." if density == 0 else f"Where residential use is allowed, net density must not exceed {density} dwelling units per acre."
        rules.append(_rule(district, "density", "Residential density", condition, NONRES_LOT_SOURCE))
    if establishment is not None:
        rules.append(_rule(district, "establishment", "Maximum establishment floor area", f"An individual establishment must not exceed {establishment * 1000:,.0f} sq ft of floor area, subject to district design-standard exceptions.", NONRES_BULK_SOURCE))
    if height is not None:
        rules.append(_rule(district, "height", "Maximum building height", f"Building height must not exceed {height} ft.", NONRES_BULK_SOURCE, "critical"))
    if coverage is not None:
        rules.append(_rule(district, "coverage", "Maximum building coverage", f"Building coverage must not exceed {coverage}% of lot area.", NONRES_BULK_SOURCE))
    setbacks = [("front", front), ("rear", rear), ("interior side", side), ("street side", street)]
    active = [f"{label} {value} ft" for label, value in setbacks if value is not None]
    if active:
        rules.append(_rule(district, "setbacks", "Minimum building setbacks", "Minimum building setbacks are " + ", ".join(active) + ".", NONRES_BULK_SOURCE, "critical"))
    if residential is not None:
        rules.append(_rule(district, "residential-separation", "Residential-district separation", f"A building must be set back at least {residential} ft from a lot line abutting a residential zoning district; apply additional height-based separation where Table 26-2D-3.1 requires it.", NONRES_BULK_SOURCE))
    if parking_front is not None or parking_street is not None:
        parts = []
        if parking_front is not None:
            parts.append(f"front {parking_front} ft")
        if parking_street is not None:
            parts.append(f"street side {parking_street} ft")
        rules.append(_rule(district, "parking-setbacks", "Minimum parking setbacks", "Surface parking minimum setbacks are " + " and ".join(parts) + ".", NONRES_BULK_SOURCE))
    rules.extend(_district_design_rules(district))
    rules.extend([
        _rule(district, "orientation", "Principal building orientation", "Orient the principal building and primary entrance toward the addressed street; screen loading docks facing arterial streets or highways as required.", GENERAL_NONRES_SOURCE),
        _rule(district, "landscape-plan", "Landscape and screening plan", "Provide a landscape and screening plan complying with MDC Division 26-7C, including the district's required buffers and equipment/refuse screening.", GENERAL_NONRES_SOURCE),
        _rule(district, "parking", "Off-street parking", "Provide the applicable automobile and bicycle parking, loading, circulation, and accessible-space requirements under MDC Division 26-7B.", GENERAL_NONRES_SOURCE),
    ])
    return rules


def _district_design_rules(district: str) -> list[dict[str, Any]]:
    if district == "CA":
        source = "MDC section 26-4B-1, Aggieville Commercial design standards"
        return [
            _rule(district, "placement", "Aggieville build-to standard", "At least 75% of each street-facing facade must be within 10 ft of the street-fronting property line, with the primary entrance oriented to the public sidewalk.", source),
            _rule(district, "core-height", "Aggieville subdistrict height", "Determine the GIS/site subdistrict. In the Core, existing buildings are generally limited to 2 stories and 35 ft and new buildings to 3 stories; corridor buildings require 3 street-facing stories and allow up to 5 stories; qualifying gateway portions may add one story.", source, "critical"),
            _rule(district, "windows", "Aggieville facade transparency", "Require street-facing window area of at least 50% for ground-floor nonresidential uses, 20% for ground-floor residential uses, and 15% above the ground floor.", source),
            _rule(district, "parking-location", "Aggieville parking location", "Locate surface parking behind buildings and outside the area between a street and the nearest street-facing building facade.", source),
        ]
    if district == "CD":
        source = "MDC section 26-4B-2, Downtown Commercial design standards"
        return [
            _rule(district, "placement", "Downtown build-to standard", "Apply the applicable 75% facade-within-10-ft standard for a single principal building or the 60% lot-width facade standard for multiple principal buildings.", source),
            _rule(district, "height", "Downtown building height", "There is no maximum base height. Principal buildings west of 3rd Street and within 50 ft of either side of the 3rd Street right-of-way must be at least 2 stories, subject to stated exceptions.", source),
            _rule(district, "parking", "Downtown surface parking", "Locate surface parking behind or beside buildings; open-to-sky parking and driving surfaces must not exceed 50% of lot area.", source),
            _rule(district, "windows", "Downtown facade transparency", "Where the design standard applies, require at least 40% ground-floor nonresidential window area, 20% ground-floor residential window area, and 15% window area above the ground floor.", source),
        ]
    if district == "MX":
        source = "MDC section 26-4B-5, Mixed Use district design standards"
        return [
            _rule(district, "parking-location", "Mixed-use parking location", "Locate surface parking behind or beside buildings; open-to-sky parking and driving surfaces must not exceed 50% of lot area.", source),
            _rule(district, "windows", "Mixed-use facade transparency", "Require at least 40% ground-floor nonresidential window area, 20% ground-floor residential window area, and 15% window area above the ground floor.", source),
            _rule(district, "open-space", "Mixed-use open space", "For a site at least 5 acres and not within 1,000 ft walking distance of a park, plaza, or similar space, provide qualifying on-site open space equal to at least 10% of gross land area.", source),
        ]
    if district == "UC":
        return [
            _rule(district, "buffer", "University district residential buffer", "Provide a Type-C buffer along every property line abutting a residential district, except along public rights-of-way.", "MDC section 26-2B-2, University & College District"),
            _rule(district, "location", "University district street location", "The district must be adjacent to a collector or arterial street, subject to the code's Kansas State roadway agreement provisions.", "MDC section 26-2B-2, University & College District"),
        ]
    return []


def _land_reserve_rules() -> list[dict[str, Any]]:
    source = "MDC section 26-2B-4, Land Reserve District"
    return [
        _rule("LR", "lot", "Land Reserve lot dimensions", "Lot area must be at least 1 acre and lot width at least 50 ft.", source),
        _rule("LR", "setbacks", "Land Reserve setbacks", "Principal and accessory structures must be set back at least 25 ft from front, side, and rear lot lines.", source, "critical"),
        _rule("LR", "height", "Land Reserve height", "Structure height must not exceed 50 ft.", source, "critical"),
        _rule("LR", "urban-edge", "Land Reserve urban-edge protection", "Maintain new barbed-wire or electric fences and a firebreak at least 40 ft from or along lot lines abutting urban-level development, as applicable.", source),
    ]


def _pud_rules(profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    attributes = (profile or {}).get("attributes") or {}
    pud_type = str(attributes.get("PUDTYPE") or "").strip()
    ordinance = str((profile or {}).get("ordinance") or "").strip()
    details = f" The GIS classification identifies type {pud_type}." if pud_type and pud_type != "Unknown" else ""
    if ordinance:
        details += f" The parcel ordinance is {ordinance}."
    source = "MDC section 26-2B-3 and the parcel's approved PUD development plan"
    return [
        _rule("PUD", "governing-plan", "Approved PUD development plan", "Apply the uses, setbacks, height, density, parking ratios, signs, open space, phasing, and conditions in the approved preliminary and final PUD plans." + details + " If the controlling plan is unavailable, report insufficient source data instead of requesting zoning thresholds from the user.", source, "critical"),
        _rule("PUD", "district-size", "Minimum PUD district size", "Require at least 0.5 acre for residential, commercial, or combined residential-commercial PUDs and at least 1 acre for industrial, industrial mixed with other uses, or manufactured-home-park PUDs.", "MDC section 26-2B-3"),
        _rule("PUD", "guarantees", "Pre-permit PUD guarantees", "Before building-permit issuance, verify required guarantees for approved landscaping, irrigation, recreational facilities, and improvements that will be delivered in later phases.", "MDC section 26-2B-3"),
    ]


def build_manhattan_rules(district: str | None, zoning_profile: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    value = str(district or "").strip().upper()
    if not value:
        return []
    if "/" in value:
        components = [component.strip() for component in value.split("/") if component.strip()]
        rules = [
            _rule(
                "split",
                "district-boundaries",
                "Split-zoning boundaries",
                f"The parcel intersects multiple zoning districts ({', '.join(components)}). Determine which portion of the proposed work lies in each district and apply that district's generated standards to that portion.",
                "City of Manhattan official zoning map",
                "critical",
            )
        ]
        for component in components:
            rules.extend(build_manhattan_rules(component, zoning_profile))
        return rules
    if value in RESIDENTIAL_STANDARDS:
        return _residential_rules(value)
    if value in NONRES_LOT_STANDARDS:
        return _nonres_rules(value)
    if value == "LR":
        return _land_reserve_rules()
    if value == "PUD":
        return _pud_rules(zoning_profile)
    return [_rule(value, "official-source", f"{value} controlling standards", "Resolve this detected district against the current Manhattan Development Code, parcel ordinance, and approved plans. If no controlling source is available, report insufficient source data and do not ask the user to provide zoning thresholds.", "Official Manhattan Development Code", "critical")]


def has_manhattan_rule_coverage(district: str | None) -> bool:
    return bool(build_manhattan_rules(district))
