"""Build review rules for every zoning classification returned by KCMO GIS."""

from __future__ import annotations

import re
from typing import Any


R_SOURCE = "KCMO Zoning and Development Code section 88-110-06"
OB_SOURCE = "KCMO Zoning and Development Code section 88-120-04"
D_SOURCE = "KCMO Zoning and Development Code section 88-130"
M_SOURCE = "KCMO Zoning and Development Code section 88-140-04"
SPECIAL_SOURCE = "KCMO Zoning and Development Code, 200 Series"
OVERLAY_SOURCE = "KCMO Zoning and Development Code, overlay district standards"

R_STANDARDS = {
    "R-80": (80000, 80000, 150, 25, 40, 25, 50, 35),
    "R-10": (10000, 10000, 85, 25, 30, 25, 30, 35),
    "R-7.5": (7500, 7500, 50, 25, 30, 25, 30, 35),
    "R-6": (6000, 6000, 50, 25, 30, 25, 30, 35),
    "R-5": (5000, 5000, 45, 25, 25, 25, 30, 35),
    "R-2.5": (4000, 2500, 40, 25, 25, 25, 25, 40),
    "R-1.5": (3000, 1500, 30, 15, 20, 25, 25, 45),
    "R-0.75": (3000, 750, 30, 15, 20, 25, 25, 60),
    "R-0.5": (3000, 500, 30, 15, 20, 25, 25, 164),
    "R-0.3": (2500, 300, 25, 15, 20, 25, 25, 235),
}

OB_STANDARDS = {
    1: (1250, 1.4, 40, 35),
    2: (750, 2.2, 50, 45),
    3: (400, 3.0, 60, 55),
    4: (300, 4.0, 70, 65),
    5: (200, 6.0, None, None),
}

D_STANDARDS = {
    1: (1250, 1.4, 40, 35),
    2: (750, 2.2, 50, 45),
    3: (400, 3.0, 60, 55),
    5: (200, 5.0, None, None),
    7: (150, 7.0, None, None),
    10: (125, 10.0, None, None),
    15: (100, 15.0, None, None),
}

M_STANDARDS = {
    1: (1.4, 40),
    2: (2.2, 50),
    3: (3.0, 60),
    4: (4.0, 70),
    5: (5.0, None),
}

OVERLAY_COMPONENTS = {"ICO", "PO", "HO", "US", "SRO"}


def _rule(
    component: str,
    key: str,
    title: str,
    condition: str,
    source: str,
    severity: str = "major",
) -> dict[str, Any]:
    return {
        "id": f"kcmo-{component.lower().replace('.', '-')}-{key}",
        "category": "zoning",
        "group": f"{component} zoning standards",
        "rule": title,
        "condition": condition,
        "severity": severity,
        "source": source,
    }


def _residential_rules(component: str) -> list[dict[str, Any]]:
    lot, per_unit, width, front_pct, front_cap, rear_pct, rear_cap, height = R_STANDARDS[component]
    return [
        _rule(component, "lot-area", "Minimum lot area", f"Lot area must be at least {lot:,} sq ft.", R_SOURCE),
        _rule(component, "unit-area", "Minimum lot area per dwelling unit", f"Provide at least {per_unit:,} sq ft of lot area per dwelling unit.", R_SOURCE),
        _rule(component, "lot-width", "Minimum lot width", f"Lot width must be at least {width} ft.", R_SOURCE),
        _rule(component, "front-setback", "Front setback", f"Front setback must be at least {front_pct}% of lot depth, but no more than {front_cap} ft is required, subject to the platted-building-line rule.", R_SOURCE),
        _rule(component, "rear-setback", "Rear setback", f"Rear setback must be at least {rear_pct}% of lot depth, but no more than {rear_cap} ft is required.", R_SOURCE),
        _rule(component, "side-setback", "Interior side setbacks", "Each interior side setback must equal at least 10% of lot width; no more than 8 ft per side is required.", R_SOURCE),
        _rule(component, "street-side", "Street-side setback", "A side lot line abutting a street requires a setback of at least 15 ft.", R_SOURCE),
        _rule(component, "height", "Maximum building height", f"Building height must not exceed {height} ft.", R_SOURCE, "critical"),
    ]


def _conditional_setback_rules(component: str, source: str) -> list[dict[str, Any]]:
    return [
        _rule(component, "front-setback", "Front setback next to an R district", "When the lot abuts an R district, apply the existing platted setback or 50% of the adjoining R-district setback as required by the code; otherwise no base front setback applies.", source),
        _rule(component, "rear-setback", "Rear setback next to an R district", "When the rear lot line abuts an R district, provide 25% of lot depth, with no more than 30 ft required; otherwise no base rear setback applies.", source),
        _rule(component, "side-setback", "Side setback next to an R district", "When a side lot line abuts an R district, apply the adjoining R-district side setback; otherwise no base interior side setback applies.", source),
    ]


def _office_business_rules(component: str, intensity: int) -> list[dict[str, Any]]:
    unit_area, far, mixed_height, other_height = OB_STANDARDS[intensity]
    rules = [
        _rule(component, "unit-area", "Single-purpose residential density", f"Single-purpose residential: at least {unit_area:,} sq ft of lot area per unit. Residential in a mixed-use building: no minimum.", OB_SOURCE),
        _rule(component, "far", "Maximum floor area ratio", f"Floor area ratio must not exceed {far:g}.", OB_SOURCE, "critical"),
        *_conditional_setback_rules(component, OB_SOURCE),
        _rule(component, "buffer", "Residential-district buffer", "Where the site abuts an R district, apply the screening and buffering standards in section 88-425.", OB_SOURCE),
    ]
    if mixed_height is not None:
        rules.extend([
            _rule(component, "mixed-height", "Mixed-use building height", f"A mixed-use building must not exceed {mixed_height} ft.", OB_SOURCE, "critical"),
            _rule(component, "other-height", "Other building height", f"All other buildings must not exceed {other_height} ft.", OB_SOURCE, "critical"),
        ])
    else:
        rules.append(_rule(component, "height", "Base height standard", "This intensity has no base maximum height; verify any overlay, airport, approved-plan, or other applicable height limit.", OB_SOURCE))
    return rules


def _downtown_rules(component: str, intensity: int) -> list[dict[str, Any]]:
    unit_area, far, commercial_height, other_height = D_STANDARDS[intensity]
    rules = [
        _rule(component, "unit-area", "Single-purpose residential density", f"Single-purpose residential: at least {unit_area:,} sq ft of lot area per unit. Mixed-use residential above the ground floor: no minimum.", D_SOURCE),
        _rule(component, "far", "Maximum floor area ratio", f"Floor area ratio must not exceed {far:g}.", D_SOURCE, "critical"),
        *_conditional_setback_rules(component, D_SOURCE),
        _rule(component, "ground-floor-height", "Ground-floor ceiling height", "New nonresidential or nonparking ground-floor space must have a minimum floor-to-ceiling height of 13 ft.", D_SOURCE),
        _rule(component, "commercial-area", "Ground-floor commercial area", "For lots under 50 ft wide, ground-floor commercial space must be the greater of 800 sq ft or 25% of lot area; for lots at least 50 ft wide, it must be at least 20% of lot area.", D_SOURCE),
        _rule(component, "principal-building", "Principal buildings", "Only one principal building is allowed unless the city has approved otherwise.", D_SOURCE),
    ]
    if commercial_height is not None:
        rules.extend([
            _rule(component, "commercial-height", "Commercial-ground-floor building height", f"A building with ground-floor commercial space must not exceed {commercial_height} ft.", D_SOURCE, "critical"),
            _rule(component, "other-height", "Other building height", f"All other buildings must not exceed {other_height} ft.", D_SOURCE, "critical"),
        ])
    else:
        rules.append(_rule(component, "height", "Base height standard", "This downtown intensity has no base maximum height; verify overlays, airport limits, and approved development plans.", D_SOURCE))
    return rules


def _manufacturing_rules(component: str, intensity: int) -> list[dict[str, Any]]:
    far, height = M_STANDARDS[intensity]
    rules = [
        _rule(component, "far", "Maximum floor area ratio", f"Floor area ratio must not exceed {far:g}.", M_SOURCE, "critical"),
        *_conditional_setback_rules(component, M_SOURCE),
    ]
    if height is None:
        rules.append(_rule(component, "height", "Base height standard", "This intensity has no base maximum height; verify airport, overlay, and approved-plan limits.", M_SOURCE))
    else:
        rules.append(_rule(component, "height", "Maximum building height", f"Building height must not exceed {height} ft.", M_SOURCE, "critical"))
    return rules


def _special_rules(component: str, ordinance: str | None) -> list[dict[str, Any]]:
    if component == "AG-R":
        return [
            _rule(component, "height", "Maximum building height", "Building height must not exceed 3 stories.", SPECIAL_SOURCE, "critical"),
            _rule(component, "house-lot", "Detached-house lot area", "A detached-house lot must contain at least 40 acres.", SPECIAL_SOURCE),
            _rule(component, "assembly-lot", "Assembly or elementary-school lot area", "A religious assembly or elementary-school site must contain at least 5 acres.", SPECIAL_SOURCE),
            _rule(component, "education-lot", "Secondary or higher-education lot area", "A secondary school or higher-education site must contain at least 10 acres.", SPECIAL_SOURCE),
            _rule(component, "setbacks", "Property-line setbacks", "Buildings must be set back at least 30 ft from property lines; qualifying detached-house decks and balconies may use a 20-ft rear setback.", SPECIAL_SOURCE),
        ]
    if component == "KCIA":
        return [
            _rule(component, "lot-area", "Minimum lot area", "Lot area must be at least 5 acres.", SPECIAL_SOURCE),
            _rule(component, "setbacks", "Property-line setbacks", "Buildings must be set back at least 30 ft from all property lines.", SPECIAL_SOURCE),
            _rule(component, "height", "Airport height limits", "Apply FAA and airport-specific height regulations; the KCIA district has no separate base maximum height.", SPECIAL_SOURCE, "critical"),
        ]

    ordinance_text = f" identified by city GIS as ordinance {ordinance}" if ordinance else " associated with the parcel"
    plan_labels = {
        "UR": "approved UR preliminary and final development plans",
        "MPD": "approved MPD preliminary development plan",
        "SC": "approved development plan and community-plan standards",
        "CXO": "approved development plan",
        "O": "parcel-specific zoning ordinance and current official zoning map",
    }
    label = plan_labels.get(component, "parcel-specific zoning approval")
    return [
        _rule(component, "governing-plan", "Governing plan standards", f"Apply the {label}{ordinance_text}. Dimensional standards must come from that controlling approval, not from user-entered values.", SPECIAL_SOURCE, "critical"),
        _rule(component, "plan-consistency", "Plan consistency", f"Compare the proposed use, site plan, height, setbacks, density, access, and conditions against the {label}; if the controlling record cannot be retrieved, report insufficient source data rather than requesting thresholds from the user.", SPECIAL_SOURCE),
    ]


def _overlay_rules(component: str, ordinance: str | None) -> list[dict[str, Any]]:
    if component == "PO":
        return [
            _rule(component, "build-to", "Pedestrian-oriented build-to line", "Buildings must abut the sidewalk or be within 5 ft of the front property line, subject to code exceptions for arcades, plazas, parks, recessed entries, and detached houses.", OVERLAY_SOURCE),
            _rule(component, "transparency", "Ground-floor transparency", "At least 60% of the ground-floor facade between 4 and 10 ft above the sidewalk must be transparent; a corner building may satisfy this on one street frontage.", OVERLAY_SOURCE),
        ]
    ordinance_text = f" City GIS identifies ordinance {ordinance}." if ordinance else ""
    labels = {
        "ICO": "approved area-specific overlay plan and design guidelines",
        "HO": "historic overlay requirements and certificate-of-appropriateness standards",
        "US": "underground-space district standards",
        "SRO": "special review overlay standards",
    }
    label = labels.get(component, "approved overlay standards")
    return [_rule(component, "overlay", f"{component} overlay requirements", f"Apply the {label}.{ordinance_text} The overlay controls where it conflicts with the base district; missing controlling records must be reported as insufficient source data.", OVERLAY_SOURCE, "critical")]


def _classify_component(component: str) -> tuple[str, int | None]:
    if component in R_STANDARDS:
        return "residential", None
    match = re.fullmatch(r"(?:O|B[1-4])-(\d)", component)
    if match and int(match.group(1)) in OB_STANDARDS:
        return "office_business", int(match.group(1))
    match = re.fullmatch(r"D(?:C|R|X)-(\d+)", component)
    if match and int(match.group(1)) in D_STANDARDS:
        return "downtown", int(match.group(1))
    match = re.fullmatch(r"M[1-4]-(\d)", component)
    if match and int(match.group(1)) in M_STANDARDS:
        return "manufacturing", int(match.group(1))
    if component in {"AG-R", "KCIA", "UR", "MPD", "SC", "CXO", "O"}:
        return "special", None
    if component in OVERLAY_COMPONENTS or re.fullmatch(r"WHO-\d+", component):
        return "overlay", None
    return "unknown", None


def build_kcmo_rules(
    classification: str | None,
    zoning_profile: dict[str, Any] | None = None,
    project_type: str | None = None,
) -> list[dict[str, Any]]:
    """Generate applicable base-district and overlay rules without user thresholds."""
    value = str(classification or "").strip().upper()
    if not value:
        return []

    ordinance = str((zoning_profile or {}).get("ordinance") or "").strip() or None
    components = [part.strip() for part in value.split("/") if part.strip()]
    rules: list[dict[str, Any]] = []
    base_components: list[str] = []

    for component in components:
        family, intensity = _classify_component(component)
        if family == "residential":
            base_components.append(component)
            rules.extend(_residential_rules(component))
        elif family == "office_business":
            base_components.append(component)
            rules.extend(_office_business_rules(component, int(intensity)))
        elif family == "downtown":
            base_components.append(component)
            rules.extend(_downtown_rules(component, int(intensity)))
        elif family == "manufacturing":
            base_components.append(component)
            rules.extend(_manufacturing_rules(component, int(intensity)))
        elif family == "special":
            base_components.append(component)
            rules.extend(_special_rules(component, ordinance))
        elif family == "overlay":
            rules.extend(_overlay_rules(component, ordinance))
        else:
            rules.append(_rule(component, "official-source", f"{component} controlling standards", "Resolve this classification against the current official zoning code, parcel ordinance, and approved plans. If no controlling source is available, report insufficient source data and do not ask the user to supply zoning thresholds.", SPECIAL_SOURCE, "critical"))

    if len(base_components) > 1:
        joined = ", ".join(base_components)
        rules.insert(0, _rule("split", "district-boundaries", "Split-zoning boundaries", f"The parcel contains multiple base districts ({joined}). Determine which portion of the proposed work lies in each district and apply that district's generated standards to that portion.", "KCMO official zoning map", "critical"))

    deduplicated: dict[str, dict[str, Any]] = {}
    for rule in rules:
        deduplicated[rule["id"]] = rule
    output = list(deduplicated.values())
    commercial_only = project_type in {
        "commercial",
        "commercial_tenant_improvement",
        "new_commercial_construction",
        "industrial",
    }
    if commercial_only:
        output = [
            rule
            for rule in output
            if not rule["id"].endswith("-unit-area")
            and rule["rule"] != "Mixed-use building height"
        ]
    return output


def has_kcmo_rule_coverage(classification: str | None) -> bool:
    return bool(build_kcmo_rules(classification))
