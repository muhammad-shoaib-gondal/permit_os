from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PermitRequirement(BaseModel):
    agency: str
    permit_name: str
    form_id: str
    fee_usd: float
    timeline_days: int
    dependencies: list[str] = Field(default_factory=list)


class DocumentRequirement(BaseModel):
    name: str
    source_agent: str
    status: str = "required"


class PermitPackage(BaseModel):
    case_id: UUID
    permits_required: list[PermitRequirement] = Field(default_factory=list)
    documents_required: list[DocumentRequirement] = Field(default_factory=list)
    total_fees_estimate_usd: float = 0.0
    estimated_timeline_days: int = 0
    filing_sequence: list[str] = Field(default_factory=list)
    audit_hash: Optional[str] = None
    rfi_draft: Optional[str] = None
