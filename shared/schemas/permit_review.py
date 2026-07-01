from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PermitCardStatus(str, Enum):
    READY = "ready"
    MISSING_DOCS = "missing_docs"
    NEEDS_REVIEW = "needs_review"
    HIGH_RISK = "high_risk"


class ProjectReadinessState(str, Enum):
    READY_TO_PREPARE = "ready_to_prepare"
    NEEDS_MORE_DOCUMENTS = "needs_more_documents"
    NEEDS_PROJECT_CHANGES = "needs_project_changes"
    HIGH_SUBMISSION_RISK = "high_submission_risk"


class ProjectFact(BaseModel):
    key: str
    label: str
    value: str
    confidence: float = 1.0
    source: str | None = None


class ProjectSummary(BaseModel):
    city: str
    project_type: str
    narrative: str
    facts: list[ProjectFact] = Field(default_factory=list)


class CandidatePermit(BaseModel):
    permit_key: str
    label: str
    agency: str
    reason: str
    confidence: float = 1.0
    required: bool = True


class PermitDocumentRequirement(BaseModel):
    key: str
    label: str
    required: bool = True
    notes: str | None = None


class PermitDocumentMatch(BaseModel):
    file_name: str
    file_type: str
    document_key: str | None = None
    matched: bool = True


class PermitFinding(BaseModel):
    severity: str
    message: str
    citation: str | None = None


class PermitReview(BaseModel):
    permit_key: str
    label: str
    agency: str
    status: PermitCardStatus = PermitCardStatus.NEEDS_REVIEW
    required_documents: list[PermitDocumentRequirement] = Field(default_factory=list)
    matched_documents: list[PermitDocumentMatch] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)
    findings: list[PermitFinding] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class CrossPermitIssue(BaseModel):
    issue: str
    severity: str
    affected_permits: list[str] = Field(default_factory=list)
    suggested_fix: str | None = None


class SubmissionReadiness(BaseModel):
    status: ProjectReadinessState = ProjectReadinessState.NEEDS_MORE_DOCUMENTS
    summary: str
    next_steps: list[str] = Field(default_factory=list)

