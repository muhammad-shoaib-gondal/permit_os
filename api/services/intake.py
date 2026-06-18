from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from shared.schemas.project_brief import ProjectBrief, ProjectType

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"
BRIEF_NAMES = ("project_brief.json", "brief.json", "ProjectBrief.json")


def _upload_dir(case_id: str) -> Path:
    path = UPLOAD_ROOT / case_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_brief_dict(raw: dict[str, Any], project_type: ProjectType) -> ProjectBrief:
    data = dict(raw)
    if "case_id" not in data:
        data["case_id"] = str(uuid4())
    data["project_type"] = project_type.value
    return ProjectBrief.model_validate(data)


def _find_brief_in_zip(zf: zipfile.ZipFile) -> dict[str, Any]:
    names = zf.namelist()
    for candidate in BRIEF_NAMES:
        match = next((n for n in names if n.endswith(candidate) or n == candidate), None)
        if match:
            return json.loads(zf.read(match))
    json_files = [n for n in names if n.lower().endswith(".json") and not n.startswith("__MACOSX")]
    if len(json_files) == 1:
        return json.loads(zf.read(json_files[0]))
    if json_files:
        for name in json_files:
            try:
                data = json.loads(zf.read(name))
                if isinstance(data, dict) and "address" in data and "project_name" in data:
                    return data
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
    raise HTTPException(
        status_code=400,
        detail="ZIP must include project_brief.json (or any JSON with project_name and address).",
    )


async def parse_intake_upload(
    file: UploadFile,
    project_type: ProjectType,
) -> tuple[ProjectBrief, str | None]:
    """Parse JSON or ZIP upload into a ProjectBrief; extract attachments to uploads/{case_id}/."""
    filename = (file.filename or "").lower()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    plan_ref: str | None = None

    if filename.endswith(".json"):
        try:
            raw = json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail="Project brief JSON must be an object.")
        brief = _load_brief_dict(raw, project_type)
        dest = _upload_dir(str(brief.case_id))
        (dest / "project_brief.json").write_bytes(content)
        return brief, plan_ref

    if filename.endswith(".zip"):
        try:
            zf = zipfile.ZipFile(BytesIO(content))
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Invalid ZIP archive.") from exc
        raw = _find_brief_in_zip(zf)
        brief = _load_brief_dict(raw, project_type)
        dest = _upload_dir(str(brief.case_id))
        zf.extractall(dest)
        for plan_name in ("site-plan.pdf", "plans/site-plan.pdf", "plan.pdf"):
            if (dest / plan_name).exists():
                plan_ref = str(dest / plan_name)
                brief.plan_pdf_url = plan_ref
                break
        if not plan_ref:
            for member in zf.namelist():
                if member.lower().endswith(".pdf"):
                    plan_ref = str(dest / member)
                    brief.plan_pdf_url = plan_ref
                    break
        return brief, plan_ref

    raise HTTPException(
        status_code=400,
        detail="Unsupported file type. Upload a .json project brief or a .zip containing project_brief.json.",
    )
