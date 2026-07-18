"""Deterministic KCMO permit type router for single_family / multifamily / commercial."""

from __future__ import annotations

from typing import Any

from shared.schemas.kcmo_intake import (
    FloodplainStatus,
    KcmoIntake,
    ProjectCategory,
    ScopeType,
)
from shared.tools.kcmo.load import catalog_by_id


def _item(
    permit_id: str,
    *,
    classification: str,
    reason: str,
    note_only: bool = False,
) -> dict[str, Any] | None:
    catalog = catalog_by_id()
    base = catalog.get(permit_id)
    if not base:
        return None
    return {
        "permit_type": permit_id,
        "permit_name": base.get("permit_name", permit_id),
        "issuing_authority": base.get("agency", "Kansas City, Missouri"),
        "jurisdiction": "kansas_city_mo",
        "requirement_status": "needs_confirmation" if note_only else classification,
        "lifecycle_status": "gathering_documents" if classification == "required" else "not_started",
        "origin": "system",
        "reason": reason,
        "recommendation_evidence": {
            "router": "kcmo_permit_router",
            "classification": classification,
            "noteOnly": note_only,
        },
        "source": base.get("source_url") or base.get("source"),
        "portal_url": base.get("portal_url"),
        "coverage_status": base.get("coverage_status", "active"),
        "dependencies": base.get("dependencies", []),
        "required_documents": [],
        "estimated_fee_usd": base.get("estimated_fee_usd"),
        "next_action": "Confirm whether this permit belongs in the working permit bundle.",
    }


def route_kcmo_permits(intake: KcmoIntake, zoning_profile: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return explainable candidate permits for a KCMO project."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(permit_id: str, classification: str, reason: str, note_only: bool = False) -> None:
        if permit_id in seen:
            return
        item = _item(permit_id, classification=classification, reason=reason, note_only=note_only)
        if item:
            seen.add(permit_id)
            results.append(item)

    floodplain_yes = intake.floodplain_status == FloodplainStatus.YES
    use_changed = bool(
        intake.existing_use
        and intake.proposed_use
        and intake.existing_use.strip().lower() != intake.proposed_use.strip().lower()
    )

    if intake.project_category == ProjectCategory.SINGLE_FAMILY:
        add(
            "residential_building",
            "required",
            "Residential building permit applies for one-/two-family work submitted under IB100 via CompassKC.",
        )
        if intake.includes_electrical:
            add("electrical", "required", "Electrical work selected in intake.")
        if intake.includes_plumbing:
            add("plumbing", "required", "Plumbing work selected in intake.")
        if intake.includes_mechanical:
            add("mechanical", "required", "Mechanical/HVAC work selected in intake.")
        if intake.scope_type == ScopeType.DEMOLITION:
            add("demolition", "required", "Scope type is demolition (IB107).")
        if floodplain_yes:
            add("floodplain_development", "required", "Floodplain status marked yes (IB120 / Chapter 28).")
        if intake.affects_public_row or intake.driveway_work:
            add(
                "right_of_way",
                "required",
                "Driveway / curb / sidewalk / right-of-way impact selected.",
            )
        if intake.owner_occupied:
            add(
                "homeowner_affidavit_note",
                "needs_confirmation",
                "Owner-occupied single-family — homeowner-occupant affidavit path may apply (IB146).",
                note_only=True,
            )

    elif intake.project_category == ProjectCategory.MULTIFAMILY:
        add(
            "multifamily_building_review",
            "required",
            "Multifamily project requires building / plan review (IB110 / IB142).",
        )
        add(
            "certificate_of_occupancy",
            "required",
            "Multifamily projects typically require Certificate of Occupancy closeout (IB139/IB165).",
        )
        units = intake.dwelling_units or 0
        if units > 1 or intake.fire_separation_involved:
            add(
                "multifamily_building_review",
                "required",
                "Multifamily/fire-separation review flagged (IB142).",
            )
        if intake.includes_fire_sprinkler_alarm or intake.sprinklered == "yes":
            add("fire_sprinkler", "required", "Fire sprinkler/alarm work indicated (IB116).")
        elif intake.sprinklered == "unknown":
            add(
                "fire_sprinkler",
                "likely_required",
                "Sprinkler status unknown — confirm whether IB116 fire protection permits apply.",
            )
        if intake.includes_electrical:
            add("electrical", "required", "Electrical work selected in intake.")
        if intake.includes_plumbing:
            add("plumbing", "required", "Plumbing work selected in intake.")
        if intake.includes_mechanical:
            add("mechanical", "required", "Mechanical/HVAC work selected in intake.")
        if floodplain_yes:
            add("floodplain_development", "required", "Floodplain status marked yes (IB120).")
        if intake.affects_public_row:
            add("public_improvement_review", "likely_required", "Public ROW / site impacts selected.")
        if intake.multiple_buildings:
            add(
                "multiple_building_data_sheet",
                "required",
                "Multiple buildings indicated — include Multiple Building Data Sheet (IB158).",
            )

    else:  # commercial
        add(
            "commercial_building",
            "required",
            "Commercial building permit path applies (IB110 / CompassKC).",
        )
        if intake.scope_type == ScopeType.TENANT_FINISH or intake.tenant_finish:
            add(
                "tenant_finish",
                "required",
                "Tenant finish / alteration selected.",
            )
        if (
            intake.scope_type == ScopeType.CHANGE_OF_USE
            or intake.change_of_occupancy == "yes"
            or use_changed
        ):
            add(
                "change_of_occupancy",
                "required",
                "Change of use/occupancy indicated (IB139/IB165).",
            )
        if intake.scope_type in (ScopeType.NEW_CONSTRUCTION, ScopeType.TENANT_FINISH, ScopeType.CHANGE_OF_USE):
            add(
                "certificate_of_occupancy",
                "required",
                "New commercial, tenant finish, or change of use typically requires CO review.",
            )
        if intake.includes_fire_sprinkler_alarm:
            add("fire_sprinkler", "required", "Fire sprinkler/alarm work indicated (IB116).")
        if intake.includes_electrical:
            add("electrical", "required", "Electrical work selected in intake.")
        if intake.includes_plumbing:
            add("plumbing", "required", "Plumbing work selected in intake.")
        if intake.includes_mechanical:
            add("mechanical", "required", "Mechanical/HVAC work selected in intake.")
        if intake.scope_type == ScopeType.DEMOLITION:
            add("demolition", "required", "Scope type is demolition (IB107).")
        if floodplain_yes:
            add("floodplain_development", "required", "Floodplain status marked yes (IB120).")
        if intake.affects_public_row:
            add(
                "public_improvement_review",
                "likely_required",
                "Public improvement / right-of-way impacts selected.",
            )

    if intake.floodplain_status == FloodplainStatus.UNKNOWN:
        # Surface as a router note via floodplain permit likely_required only when yes;
        # data gap is handled by site tools. Keep router silent here.
        pass

    # Attach zoning district hint when available
    district = (zoning_profile or {}).get("district")
    if district:
        for item in results:
            evidence = dict(item.get("recommendation_evidence") or {})
            evidence["zoningDistrict"] = district
            item["recommendation_evidence"] = evidence

    return results
