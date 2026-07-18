from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.services.project_service import (
    add_project_file,
    analyze_project,
    create_project,
    delete_project,
    delete_project_file,
    get_builtin_rules,
    get_builtin_rules_for_project,
    get_project_context,
    get_project,
    get_project_rules,
    add_project_permit,
    list_project_permits,
    list_projects,
    refresh_project_zoning,
    save_project_rules,
    suggest_rules,
    update_project_permit,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


class CustomRuleBody(BaseModel):
    id: str
    category: str = "custom"
    rule: str
    condition: str = ""
    severity: str = "warning"
    enabled: bool = True
    area: str | None = None
    permitType: str | None = None
    source: str | None = None


class CreateProjectBody(BaseModel):
    name: str
    address: str
    projectType: str = "commercial"
    jurisdiction: str = "kansas_city_mo"
    area: str | None = None
    scope: dict[str, bool] = Field(default_factory=dict)
    intake: dict[str, Any] = Field(default_factory=dict)
    customRules: list[CustomRuleBody] = Field(default_factory=list)


class UpdateProjectBody(BaseModel):
    name: str | None = None
    address: str | None = None
    projectType: str | None = None
    jurisdiction: str | None = None
    area: str | None = None
    scope: dict[str, bool] | None = None
    intake: dict[str, Any] | None = None
    customRules: list[CustomRuleBody] | None = None


class ChecklistPatchBody(BaseModel):
    status: str | None = None
    notes: str | None = None
    matchedFileId: str | None = None


class AnalyzeProjectBody(BaseModel):
    modules: list[str] = Field(default_factory=list)


class ProjectPermitBody(BaseModel):
    permitType: str | None = None
    permitName: str | None = None
    issuingAuthority: str | None = None
    jurisdiction: str | None = None
    requirementStatus: str | None = None
    lifecycleStatus: str | None = None
    reason: str | None = None
    source: str | None = None
    portalUrl: str | None = None
    coverageStatus: str | None = None
    parentPermitId: str | None = None
    dependencies: list[str] | None = None
    requiredDocuments: list[str] | None = None
    assignedEmployee: str | None = None
    assignedContractor: str | None = None
    estimatedFeeUsd: int | None = None
    actualFeeUsd: int | None = None
    applicationNumber: str | None = None
    issuedNumber: str | None = None
    currentBlocker: str | None = None
    nextAction: str | None = None


@router.get("")
async def get_projects():
    return await list_projects()


@router.post("")
async def post_project(body: CreateProjectBody):
    return await create_project(body.model_dump())


@router.get("/{project_id}")
async def get_project_by_id(project_id: str):
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}")
async def put_project(project_id: str, body: UpdateProjectBody):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    project = await update_project(project_id, data)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/resolve-zoning")
async def resolve_project_zoning(project_id: str):
    project = await refresh_project_zoning(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
async def remove_project(project_id: str):
    ok = await delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}


@router.post("/{project_id}/files")
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    file_type: str | None = Form(None),
    is_primary_brief: bool = Form(False),
    document_label: str | None = Form(None),
    file_sections: str | None = Form(None),
):
    result = await add_project_file(
        project_id, file, file_type, is_primary_brief, document_label=document_label, file_sections=file_sections
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.delete("/{project_id}/files/{file_id}")
async def remove_file(project_id: str, file_id: str):
    ok = await delete_project_file(project_id, file_id)
    if not ok:
        raise HTTPException(status_code=404, detail="File not found")
    return {"deleted": True}


@router.get("/{project_id}/rules")
async def get_rules(project_id: str):
    rules = await get_project_rules(project_id)
    if rules is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project = await get_project_context(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    builtin = await get_builtin_rules_for_project(
        project["jurisdiction"],
        area=project.get("area"),
        project_type=project.get("projectType"),
        zoning_profile=project.get("zoningProfile"),
    )
    return {"customRules": rules, "builtinRules": builtin}


@router.post("/{project_id}/rules")
async def post_rules(project_id: str, rules: list[CustomRuleBody]):
    saved = await save_project_rules(project_id, [r.model_dump() for r in rules])
    if saved is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"customRules": saved}


@router.post("/{project_id}/suggest-rules")
async def post_suggest_rules(project_id: str):
    return {"rules": await suggest_rules(project_id)}


@router.post("/{project_id}/analyze")
async def run_analysis(project_id: str, body: AnalyzeProjectBody | None = None):
    return await analyze_project(project_id, modules=(body.modules if body else None))


@router.get("/{project_id}/permits")
async def get_permits(project_id: str):
    permits = await list_project_permits(project_id)
    if permits is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"permits": permits}


@router.post("/{project_id}/permits")
async def post_permit(project_id: str, body: ProjectPermitBody):
    permit = await add_project_permit(project_id, body.model_dump(exclude_none=True))
    if permit is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return permit


@router.patch("/{project_id}/permits/{permit_id}")
async def patch_permit(project_id: str, permit_id: str, body: ProjectPermitBody):
    permit = await update_project_permit(project_id, permit_id, body.model_dump(exclude_none=True))
    if permit is None:
        raise HTTPException(status_code=404, detail="Permit not found")
    return permit


@router.get("/{project_id}/checklist")
async def get_checklist(project_id: str):
    from api.services.checklist_service import list_project_checklist

    items = await list_project_checklist(project_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"items": items}


@router.post("/{project_id}/checklist/rebuild")
async def rebuild_checklist(project_id: str):
    from api.services.checklist_service import rebuild_project_checklist

    items = await rebuild_project_checklist(project_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"items": items}


@router.patch("/{project_id}/checklist/{item_id}")
async def patch_checklist_item(project_id: str, item_id: str, body: ChecklistPatchBody):
    from api.services.checklist_service import update_checklist_item

    item = await update_checklist_item(project_id, item_id, body.model_dump(exclude_none=True))
    if item is None:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    return item
