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
    list_projects,
    save_project_rules,
    suggest_rules,
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


class CreateProjectBody(BaseModel):
    name: str
    address: str
    projectType: str = "multifamily_residential"
    jurisdiction: str = "austin_tx"
    area: str | None = None
    customRules: list[CustomRuleBody] = Field(default_factory=list)


class UpdateProjectBody(BaseModel):
    name: str | None = None
    address: str | None = None
    projectType: str | None = None
    jurisdiction: str | None = None
    area: str | None = None
    customRules: list[CustomRuleBody] | None = None


class AnalyzeProjectBody(BaseModel):
    modules: list[str] = Field(default_factory=list)


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
        project["jurisdiction"], area=project.get("area"), project_type=project.get("projectType")
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
