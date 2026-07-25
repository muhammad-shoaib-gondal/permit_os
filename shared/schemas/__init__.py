"""EstatePermit shared Pydantic schemas."""

from shared.schemas.case import (
    AuditEvent,
    CaseStatus,
    Conflict,
    HumanAction,
    PermitCaseSummary,
    ReadinessScore,
)
from shared.schemas.package import DocumentRequirement, PermitPackage, PermitRequirement
from shared.schemas.permit_review import (
    CandidatePermit,
    CrossPermitIssue,
    PermitCardStatus,
    PermitDocumentMatch,
    PermitDocumentRequirement,
    PermitFinding,
    PermitReview,
    ProjectFact,
    ProjectReadinessState,
    ProjectSummary,
    SubmissionReadiness,
)
from shared.schemas.project_brief import BlockSetback, ProjectBrief, ProjectType
from shared.schemas.reports import (
    BuildingSafetyReport,
    CheckResult,
    CheckStatus,
    JurisdictionInfo,
    JurisdictionReport,
    ReadinessImpact,
    SiteEnvironmentalReport,
    ZoningInfo,
)

__all__ = [
    "AuditEvent",
    "BlockSetback",
    "BuildingSafetyReport",
    "CandidatePermit",
    "CaseStatus",
    "CheckResult",
    "CheckStatus",
    "Conflict",
    "CrossPermitIssue",
    "DocumentRequirement",
    "HumanAction",
    "JurisdictionInfo",
    "JurisdictionReport",
    "PermitCardStatus",
    "PermitCaseSummary",
    "PermitDocumentMatch",
    "PermitDocumentRequirement",
    "PermitFinding",
    "PermitPackage",
    "PermitReview",
    "PermitRequirement",
    "ProjectFact",
    "ProjectBrief",
    "ProjectReadinessState",
    "ProjectSummary",
    "ProjectType",
    "ReadinessImpact",
    "ReadinessScore",
    "SiteEnvironmentalReport",
    "SubmissionReadiness",
    "ZoningInfo",
]
