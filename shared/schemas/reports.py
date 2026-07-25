from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


class ReadinessImpact(str, Enum):
    READY = "ready"
    NEEDS_CHANGES = "needs_changes"
    BLOCKED = "blocked"


class CheckResult(BaseModel):
    rule_id: Optional[str] = None
    permit_type: Optional[str] = None
    permit_name: Optional[str] = None
    rule: str
    status: CheckStatus
    citation: str
    detail: str
    category: Optional[str] = None
    evaluator: Optional[str] = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)


class JurisdictionInfo(BaseModel):
    name: str
    type: str
    codes_applicable: list[str] = Field(default_factory=list)


class ZoningInfo(BaseModel):
    district: str
    permitted_use: str
    by_right: bool


class JurisdictionReport(BaseModel):
    case_id: UUID
    summary: str
    readiness_impact: ReadinessImpact
    jurisdictions: list[JurisdictionInfo] = Field(default_factory=list)
    zoning: Optional[ZoningInfo] = None
    checks: list[CheckResult] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class BuildingSafetyReport(BaseModel):
    case_id: UUID
    summary: str
    readiness_impact: ReadinessImpact
    checks: list[CheckResult] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class SiteEnvironmentalReport(BaseModel):
    case_id: UUID
    summary: str
    readiness_impact: ReadinessImpact
    environmental_checks: list[CheckResult] = Field(default_factory=list)
    utility_checks: list[CheckResult] = Field(default_factory=list)
    additional_permits: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
