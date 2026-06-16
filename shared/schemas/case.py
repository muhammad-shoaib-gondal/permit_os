from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ReadinessScore(str, Enum):
    READY = "READY"
    NEEDS_CHANGES = "NEEDS_CHANGES"
    BLOCKED = "BLOCKED"


class CaseStatus(str, Enum):
    INTAKE = "INTAKE"
    ANALYZING = "ANALYZING"
    MERGING = "MERGING"
    PACKAGING = "PACKAGING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED_FOR_FILING = "APPROVED_FOR_FILING"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    ERROR = "ERROR"


class Conflict(BaseModel):
    agents: list[str]
    issue: str
    severity: str
    suggested_fix: str


class HumanAction(BaseModel):
    action: str
    description: str
    priority: str = "normal"


class AuditEvent(BaseModel):
    timestamp: str
    agent_id: str
    event_type: str
    message_id: Optional[str] = None
    payload_hash: Optional[str] = None
    human_id: Optional[str] = None
    detail: Optional[str] = None


class PermitCaseSummary(BaseModel):
    case_id: UUID
    project_name: str
    status: CaseStatus = CaseStatus.INTAKE
    readiness_score: ReadinessScore = ReadinessScore.NEEDS_CHANGES
    conflicts: list[Conflict] = Field(default_factory=list)
    human_actions_required: list[HumanAction] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    executive_summary: Optional[str] = None
    band_room_id: Optional[str] = None
