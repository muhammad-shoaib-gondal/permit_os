from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(512))
    project_type: Mapped[str] = mapped_column(String(50), default="multifamily_residential")
    jurisdiction: Mapped[str] = mapped_column(String(50), default="austin_tx")
    area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zoning_status: Mapped[str] = mapped_column(String(50), default="pending")
    zoning_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    zoning_warnings: Mapped[list] = mapped_column(JSON, default=list)
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    permit_answers: Mapped[dict] = mapped_column(JSON, default=dict)
    custom_rules: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    files: Mapped[list["ProjectFile"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    cases: Mapped[list["PermitCase"]] = relationship(back_populates="project")
    permits: Mapped[list["ProjectPermit"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectFile(Base):
    __tablename__ = "project_files"

    file_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.project_id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(50), default="other")
    size: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str] = mapped_column(String(1024))
    is_primary_brief: Mapped[bool] = mapped_column(default=False)
    document_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_sections: Mapped[list] = mapped_column(JSON, default=list)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    permit_types: Mapped[list] = mapped_column(JSON, default=list)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project: Mapped["Project"] = relationship(back_populates="files")


class ProjectPermit(Base):
    __tablename__ = "project_permits"

    permit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.project_id"), index=True)
    permit_type: Mapped[str] = mapped_column(String(100), index=True)
    permit_name: Mapped[str] = mapped_column(String(255))
    issuing_authority: Mapped[str] = mapped_column(String(255), default="")
    jurisdiction: Mapped[str] = mapped_column(String(50), default="")
    requirement_status: Mapped[str] = mapped_column(String(50), default="suggested")
    lifecycle_status: Mapped[str] = mapped_column(String(80), default="not_started")
    origin: Mapped[str] = mapped_column(String(50), default="system")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    portal_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    coverage_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parent_permit_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    required_documents: Mapped[list] = mapped_column(JSON, default=list)
    assigned_employee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_contractor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estimated_fee_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_fee_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issued_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    application_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issuance_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_blocker: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project: Mapped["Project"] = relationship(back_populates="permits")


class PermitCase(Base):
    __tablename__ = "permit_cases"

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.project_id"), nullable=True, index=True)
    project_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="INTAKE")
    brief: Mapped[dict] = mapped_column(JSON)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audit_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project: Mapped["Project | None"] = relationship(back_populates="cases")


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
