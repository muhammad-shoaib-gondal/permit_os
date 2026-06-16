from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProjectType(str, Enum):
    MULTIFAMILY_RESIDENTIAL = "multifamily_residential"
    SINGLE_FAMILY = "single_family"
    COMMERCIAL = "commercial"
    MIXED_USE = "mixed_use"
    INDUSTRIAL = "industrial"


class BlockSetback(BaseModel):
    block_id: str
    side: str
    required_ft: float
    actual_ft: float


class ProjectBrief(BaseModel):
    case_id: UUID = Field(default_factory=uuid4)
    project_name: str
    address: str
    project_type: ProjectType = ProjectType.MULTIFAMILY_RESIDENTIAL
    units: int
    stories: int
    gross_sqft: int
    lot_sqft: int
    parking_spaces: int
    plan_pdf_url: Optional[str] = None
    notes: Optional[str] = None
    blocks: list[BlockSetback] = Field(default_factory=list)

    @classmethod
    def riverside_residences_demo(cls) -> "ProjectBrief":
        """Demo scenario: 50-unit Austin project with Block B setback violation."""
        return cls(
            project_name="Riverside Residences",
            address="1200 Riverside Dr, Austin, TX 78704",
            project_type=ProjectType.MULTIFAMILY_RESIDENTIAL,
            units=50,
            stories=4,
            gross_sqft=52000,
            lot_sqft=85000,
            parking_spaces=75,
            notes="Block B east wall at 8ft side setback (10ft required per Austin LDC 25-2-491)",
            blocks=[
                BlockSetback(
                    block_id="Block B",
                    side="east",
                    required_ft=10.0,
                    actual_ft=8.0,
                )
            ],
        )
