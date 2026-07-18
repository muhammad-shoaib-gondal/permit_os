"""KCMO zoning feasibility checks (deterministic + DATA_GAP when facts missing)."""

from __future__ import annotations

from typing import Any

from shared.schemas.kcmo_intake import FindingStatus, KcmoFinding, KcmoIntake, ProjectCategory
from shared.tools.kcmo.load import load_kcmo_json


def _finding(
    status: FindingStatus,
    finding: str,
    explanation: str,
    citation: str = "Chapter 88 Zoning and Development Code",
    required: list[str] | None = None,
    next_action: str = "",
) -> KcmoFinding:
    return KcmoFinding(
        status=status,
        module="zoning",
        finding=finding,
        explanation=explanation,
        citation=citation,
        source_type="code",
        required_user_data=required or [],
        next_action=next_action,
    )


def check_kcmo_city_limits(zoning_profile: dict[str, Any] | None) -> KcmoFinding:
    if not zoning_profile:
        return _finding(
            FindingStatus.DATA_GAP,
            "KCMO city-limit / parcel match not confirmed",
            "Resolve the address against KCMO Parcel Viewer / zoning GIS.",
            citation="KCMO Parcel Viewer",
            required=["Valid Kansas City, MO address"],
            next_action="Re-run address/zoning resolve.",
        )
    district = zoning_profile.get("district")
    if district:
        return _finding(
            FindingStatus.PASS,
            f"Parcel matched in Kansas City, MO (district {district})",
            f"GIS matched address to district {district}.",
            citation="KCMO Zoning GIS / Parcel Viewer",
        )
    return _finding(
        FindingStatus.WARN,
        "Address geocoded but zoning district missing",
        "Confirm the parcel in Parcel Viewer before relying on zoning conclusions.",
        citation="KCMO Parcel Viewer",
    )


def check_kcmo_use_allowed(intake: KcmoIntake, zoning_profile: dict[str, Any] | None) -> KcmoFinding:
    district = (zoning_profile or {}).get("district")
    proposed = (intake.proposed_use or "").strip()
    if not district:
        return _finding(
            FindingStatus.DATA_GAP,
            "Zoning district unknown — cannot evaluate use permission",
            "Need a resolved zoning district before use feasibility can be scored.",
            required=["Zoning district"],
        )
    if not proposed:
        return _finding(
            FindingStatus.DATA_GAP,
            "Proposed use missing",
            "Enter proposed use to evaluate allowed / conditional / prohibited status.",
            required=["Proposed use"],
            next_action="Add proposed use on the project intake form.",
        )

    zoning = load_kcmo_json("zoning_rules.json")
    assert isinstance(zoning, dict)
    districts = zoning.get("districts") or {}
    # Partial tables: if district encoded, treat residential/commercial categories as WARN pending full use table
    if district in districts or any(district.startswith(k.split("-")[0]) for k in districts):
        category = intake.project_category.value
        return _finding(
            FindingStatus.WARN,
            f"Proposed use '{proposed}' needs district use-table confirmation in {district}",
            (
                f"District {district} has partial encoded standards. Confirm whether '{proposed}' "
                f"({category}) is permitted, conditional, or prohibited under Chapter 88."
            ),
            citation="Chapter 88 / Municode",
            next_action="Verify use permission in Chapter 88 use tables for this district.",
        )
    return _finding(
        FindingStatus.DATA_GAP,
        f"No encoded use table for district {district}",
        "Use permission cannot be auto-scored for this district yet.",
        required=["District use table coverage"],
        next_action="Manually verify proposed use against Chapter 88.",
    )


def check_kcmo_dimensional_standards(
    intake: KcmoIntake, zoning_profile: dict[str, Any] | None
) -> list[KcmoFinding]:
    findings: list[KcmoFinding] = []
    district = (zoning_profile or {}).get("district")
    if not district:
        findings.append(
            _finding(
                FindingStatus.DATA_GAP,
                "Cannot check setbacks/height/density without zoning district",
                "Resolve zoning first.",
                required=["Zoning district"],
            )
        )
        return findings

    if intake.building_area_sqft is None:
        findings.append(
            _finding(
                FindingStatus.DATA_GAP,
                "Building area missing — FAR/coverage checks incomplete",
                "Provide building area (sq ft).",
                required=["Building area"],
            )
        )
    if intake.stories is None:
        findings.append(
            _finding(
                FindingStatus.DATA_GAP,
                "Stories missing — height compliance cannot be confirmed",
                "Provide number of stories.",
                required=["Number of stories"],
            )
        )
    if intake.project_category == ProjectCategory.MULTIFAMILY and not intake.dwelling_units:
        findings.append(
            _finding(
                FindingStatus.DATA_GAP,
                "Dwelling unit count missing — density check incomplete",
                "Provide number of dwelling units.",
                required=["Number of dwelling units"],
            )
        )

    if intake.building_area_sqft and intake.stories is not None:
        findings.append(
            _finding(
                FindingStatus.WARN,
                f"Dimensional standards for {district} require plan-based confirmation",
                (
                    "Setbacks, height, and lot coverage need site-plan dimensions. "
                    "Encoded district standards (when available) should be compared to the submitted plan."
                ),
                citation="Chapter 88 dimensional standards",
                next_action="Upload a dimensioned site plan and confirm against district tables.",
            )
        )
    return findings


def check_kcmo_parking_loading(intake: KcmoIntake, zoning_profile: dict[str, Any] | None) -> list[KcmoFinding]:
    district = (zoning_profile or {}).get("district")
    if intake.scope_type.value in ("new_construction", "addition") or intake.change_in_unit_count:
        return [
            _finding(
                FindingStatus.WARN,
                "Parking/loading requirements may be triggered",
                (
                    "Chapter 88 parking/loading applies to new buildings/uses and expansions that add "
                    "units, floor area, or other measurement units."
                ),
                citation="Chapter 88-420 Parking and Loading",
                next_action="Confirm parking/loading counts against Chapter 88-420.",
            )
        ]
    if not district:
        return [
            _finding(
                FindingStatus.DATA_GAP,
                "Parking/loading not evaluated — district unknown",
                "Resolve zoning district first.",
                required=["Zoning district"],
            )
        ]
    return [
        _finding(
            FindingStatus.PASS,
            "No expansion trigger selected for parking/loading auto-check",
            "If the project enlarges use/area/units, re-evaluate Chapter 88-420.",
            citation="Chapter 88-420 Parking and Loading",
        )
    ]


def check_kcmo_zoning_overlays(zoning_profile: dict[str, Any] | None) -> list[KcmoFinding]:
    profile = zoning_profile or {}
    extras = []
    for key in ("overlay", "historic", "pud", "ordinance"):
        if profile.get(key):
            extras.append(f"{key}={profile[key]}")
    if profile.get("ordinance"):
        return [
            _finding(
                FindingStatus.WARN,
                "Site-specific ordinance / overlay conditions may apply",
                f"GIS returned additional attributes: {', '.join(extras) or 'see zoning profile'}.",
                citation="KCMO Zoning GIS",
                next_action="Review overlay/special district conditions before filing.",
            )
        ]
    return [
        _finding(
            FindingStatus.DATA_GAP,
            "Overlay / special-district status not fully verified",
            "Confirm overlays, historic districts, and nonconforming status in Parcel Viewer.",
            citation="KCMO Parcel Viewer",
            required=["Overlay verification"],
        )
    ]


def run_kcmo_zoning_checks(
    intake: KcmoIntake, zoning_profile: dict[str, Any] | None
) -> list[KcmoFinding]:
    findings = [
        check_kcmo_city_limits(zoning_profile),
        check_kcmo_use_allowed(intake, zoning_profile),
    ]
    findings.extend(check_kcmo_dimensional_standards(intake, zoning_profile))
    findings.extend(check_kcmo_parking_loading(intake, zoning_profile))
    findings.extend(check_kcmo_zoning_overlays(zoning_profile))
    return findings
