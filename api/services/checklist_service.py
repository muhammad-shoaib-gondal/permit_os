"""Persistent KCMO ready-to-file checklist with filename auto-match."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.models import Project, ProjectChecklistItem, ProjectFile
from api.services.case_service import SessionLocal
from shared.schemas.kcmo_intake import KcmoIntake
from shared.tools.kcmo.checklist_match import match_filename_to_checklist_keys
from shared.tools.kcmo.load import load_kcmo_json

# Re-export for callers
__all__ = [
    "rebuild_project_checklist",
    "list_project_checklist",
    "update_checklist_item",
    "match_filename_to_checklist_keys",
]


def _intake_from_project(project: Project) -> KcmoIntake:
    raw = dict(project.intake or {})
    if not raw.get("project_category"):
        pt = project.project_type or "commercial"
        if pt == "single_family":
            raw["project_category"] = "single_family"
        elif pt in {"multifamily_residential", "mixed_use"}:
            raw["project_category"] = "multifamily"
        else:
            raw["project_category"] = "commercial"
    try:
        return KcmoIntake.model_validate(raw)
    except Exception:
        return KcmoIntake(project_category=raw.get("project_category", "commercial"))


def _when_matches(when: dict[str, Any] | None, intake: KcmoIntake) -> bool:
    if not when:
        return True
    if when.get("basement_finish") and not intake.basement_finish:
        return False
    if when.get("owner_occupied") and not intake.owner_occupied:
        return False
    if when.get("multiple_buildings") and not intake.multiple_buildings:
        return False
    if when.get("includes_fire_sprinkler_alarm") and not (
        intake.includes_fire_sprinkler_alarm or intake.sprinklered == "yes"
    ):
        return False
    if when.get("floodplain_yes") and intake.floodplain_status.value != "yes":
        return False
    if when.get("scope_demolition") and intake.scope_type.value != "demolition":
        return False
    if when.get("any_trade") and not (
        intake.includes_electrical or intake.includes_plumbing or intake.includes_mechanical
    ):
        return False
    return True


def _match_file(files: list[ProjectFile], match_keys: list[str], keywords: dict[str, list[str]]) -> str | None:
    if not match_keys:
        return None
    for file in files:
        name = f"{file.name} {file.document_label or ''}".lower()
        for key in match_keys:
            for token in keywords.get(key, [key.replace("_", " ")]):
                if token.lower() in name:
                    return file.file_id
    return None


def _serialize(item: ProjectChecklistItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "projectId": item.project_id,
        "caseId": item.case_id,
        "itemKey": item.item_key,
        "label": item.label,
        "category": item.category,
        "requiredFor": item.required_for or [],
        "sourceTitle": item.source_title,
        "sourceUrl": item.source_url,
        "sourceSection": item.source_section,
        "status": item.status,
        "matchedFileId": item.matched_file_id,
        "notes": item.notes,
        "createdAt": item.created_at.isoformat() if item.created_at else None,
        "updatedAt": item.updated_at.isoformat() if item.updated_at else None,
    }


async def rebuild_project_checklist(project_id: str) -> list[dict[str, Any]] | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.files), selectinload(Project.checklist_items))
        )
        project = result.scalar_one_or_none()
        if not project:
            return None
        if project.jurisdiction != "kansas_city_mo":
            return []

        intake = _intake_from_project(project)
        pack = load_kcmo_json("document_checklists.json")
        assert isinstance(pack, dict)
        keywords = pack.get("match_keywords") or {}
        existing = {i.item_key: i for i in (project.checklist_items or [])}
        keep_keys: set[str] = set()
        now = datetime.now(timezone.utc)

        for spec in pack.get("items", []):
            required_for = list(spec.get("required_for") or [])
            if intake.project_category.value not in required_for:
                continue
            if not _when_matches(spec.get("when"), intake):
                continue
            key = spec["id"]
            keep_keys.add(key)
            matched = _match_file(list(project.files or []), list(spec.get("match_keys") or []), keywords)
            item = existing.get(key)
            if not item:
                item = ProjectChecklistItem(
                    id=str(uuid4()),
                    project_id=project.project_id,
                    item_key=key,
                    label=spec["label"],
                    category=intake.project_category.value,
                    required_for=required_for,
                    source_title=spec.get("source_title"),
                    source_url=spec.get("source_url"),
                    status="uploaded" if matched else "missing",
                    matched_file_id=matched,
                    created_at=now,
                    updated_at=now,
                )
                session.add(item)
            else:
                # Preserve waived / not_applicable / user notes
                if item.status not in {"waived", "not_applicable"}:
                    if matched:
                        item.status = "uploaded"
                        item.matched_file_id = matched
                    elif item.status == "uploaded" and not matched:
                        item.status = "missing"
                        item.matched_file_id = None
                item.label = spec["label"]
                item.source_title = spec.get("source_title")
                item.source_url = spec.get("source_url")
                item.updated_at = now

        for key, item in existing.items():
            if key not in keep_keys and item.status not in {"waived", "not_applicable"}:
                await session.delete(item)

        await session.commit()

        result = await session.execute(
            select(ProjectChecklistItem).where(ProjectChecklistItem.project_id == project_id)
        )
        items = result.scalars().all()
        return [_serialize(i) for i in sorted(items, key=lambda x: x.label)]


async def list_project_checklist(project_id: str) -> list[dict[str, Any]] | None:
    async with SessionLocal() as session:
        project = await session.get(Project, project_id)
        if not project:
            return None
    items = await rebuild_project_checklist(project_id)
    return items


async def update_checklist_item(
    project_id: str, item_id: str, data: dict[str, Any]
) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ProjectChecklistItem).where(
                ProjectChecklistItem.project_id == project_id,
                ProjectChecklistItem.id == item_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return None
        if "status" in data and data["status"] is not None:
            item.status = data["status"]
        if "notes" in data:
            item.notes = data["notes"]
        if "matchedFileId" in data:
            item.matched_file_id = data["matchedFileId"]
        item.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(item)
        return _serialize(item)

