"""Structured KCMO intake fields for single_family / multifamily / commercial."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProjectCategory(str, Enum):
    SINGLE_FAMILY = "single_family"
    MULTIFAMILY = "multifamily"
    COMMERCIAL = "commercial"


class ScopeType(str, Enum):
    NEW_CONSTRUCTION = "new_construction"
    ADDITION = "addition"
    ALTERATION = "alteration"
    REPAIR = "repair"
    TENANT_FINISH = "tenant_finish"
    CHANGE_OF_USE = "change_of_use"
    DEMOLITION = "demolition"


class FloodplainStatus(str, Enum):
    UNKNOWN = "unknown"
    YES = "yes"
    NO = "no"


class FindingStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    DATA_GAP = "data_gap"


class KcmoFinding(BaseModel):
    status: FindingStatus
    module: str
    finding: str
    explanation: str
    citation: str = ""
    source_type: str = "information_bulletin"
    required_user_data: list[str] = Field(default_factory=list)
    next_action: str = ""


class KcmoIntake(BaseModel):
    """Structured intake used by the KCMO permit router and scoring tools."""

    project_category: ProjectCategory = ProjectCategory.COMMERCIAL
    scope_type: ScopeType = ScopeType.ALTERATION
    parcel_lot_number: Optional[str] = None
    existing_use: Optional[str] = None
    proposed_use: Optional[str] = None
    estimated_valuation_usd: Optional[int] = None
    building_area_sqft: Optional[int] = None
    stories: Optional[int] = None
    floodplain_status: FloodplainStatus = FloodplainStatus.UNKNOWN
    includes_electrical: bool = False
    includes_plumbing: bool = False
    includes_mechanical: bool = False
    includes_fire_sprinkler_alarm: bool = False
    affects_public_row: bool = False

    # Single-family
    owner_occupied: Optional[bool] = None
    dwelling_type: Optional[Literal["one_family", "two_family"]] = None
    residential_work_type: Optional[Literal["addition", "remodel", "new_home"]] = None
    basement_finish: bool = False
    accessory_structure: bool = False
    driveway_work: bool = False

    # Multifamily
    dwelling_units: Optional[int] = None
    multifamily_form: Optional[Literal["apartments", "townhomes", "mixed_use_residential"]] = None
    fire_separation_involved: Optional[bool] = None
    sprinklered: Optional[Literal["yes", "no", "unknown"]] = None
    change_in_unit_count: bool = False
    multiple_buildings: bool = False

    # Commercial
    business_use_type: Optional[str] = None
    tenant_finish: bool = False
    shell_building: bool = False
    change_of_occupancy: Optional[Literal["yes", "no", "unknown"]] = None
    occupancy_group: Optional[str] = None
    construction_type: Optional[str] = None
    public_access: bool = False

    notes: Optional[str] = None

    def to_legacy_scope(self) -> dict[str, bool]:
        """Map structured intake onto the existing boolean scope flags."""
        scope = {
            "new_construction": self.scope_type == ScopeType.NEW_CONSTRUCTION,
            "addition": self.scope_type == ScopeType.ADDITION,
            "alteration": self.scope_type in (ScopeType.ALTERATION, ScopeType.TENANT_FINISH),
            "repair": self.scope_type == ScopeType.REPAIR,
            "demolition": self.scope_type == ScopeType.DEMOLITION,
            "structural_work": False,
            "electrical_work": self.includes_electrical,
            "plumbing_work": self.includes_plumbing,
            "mechanical_hvac_work": self.includes_mechanical,
            "fire_alarm_sprinkler_work": self.includes_fire_sprinkler_alarm
            or (self.sprinklered == "yes"),
            "signs": False,
            "change_use_occupancy": self.scope_type == ScopeType.CHANGE_OF_USE
            or self.change_of_occupancy == "yes"
            or (
                bool(self.existing_use)
                and bool(self.proposed_use)
                and self.existing_use.strip().lower() != self.proposed_use.strip().lower()
            ),
            "grading_land_disturbance": False,
            "driveway_sidewalk_row": self.affects_public_row or self.driveway_work,
            "solar_battery_generator_ev": False,
            "water_sewer_connections": False,
        }
        return scope

    def category_to_project_type(self) -> str:
        if self.project_category == ProjectCategory.SINGLE_FAMILY:
            return "single_family"
        if self.project_category == ProjectCategory.MULTIFAMILY:
            return "multifamily_residential"
        if self.scope_type == ScopeType.TENANT_FINISH or self.tenant_finish:
            return "commercial_tenant_improvement"
        if self.scope_type == ScopeType.NEW_CONSTRUCTION:
            return "new_commercial_construction"
        return "commercial"
