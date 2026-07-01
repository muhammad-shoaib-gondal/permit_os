from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
import re

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.models import PermitCase, Project, ProjectFile
from api.services.case_service import SessionLocal, start_case_async
from api.services.intake import parse_intake_upload
from shared.schemas.project_brief import ProjectBrief, ProjectType
from shared.tools.knowledge import JURISDICTION_PATHS, jurisdiction_context, load_json

PROJECT_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "projects"

FILE_TYPE_MAP = {
    ".json": "brief_json",
    ".zip": "brief_json",
    ".pdf": "site_plan",
    ".doc": "other",
    ".docx": "other",
    ".png": "floor_plan",
    ".jpg": "floor_plan",
    ".jpeg": "floor_plan",
    ".dwg": "other",
}

ANALYSIS_MODULES = {
    "zoning": {
        "label": "Zoning",
        "required_any_of": ["site_plan", "survey", "code_analysis", "other"],
        "recommended_file_types": ["site_plan", "survey", "code_analysis"],
        "summary": "Upload a site plan, survey, zoning memo, or another zoning-related document.",
    },
    "building": {
        "label": "Building",
        "required_any_of": ["floor_plan", "elevation", "code_analysis", "other"],
        "recommended_file_types": ["floor_plan", "elevation", "code_analysis"],
        "summary": "Upload a floor plan, elevations, code analysis, or another building package document.",
    },
    "fire": {
        "label": "Fire / Life Safety",
        "required_any_of": ["fire_plan", "floor_plan", "other"],
        "recommended_file_types": ["fire_plan", "floor_plan"],
        "summary": "Upload a fire/life-safety plan, floor plan, or another fire review document.",
    },
    "site": {
        "label": "Site / Utilities",
        "required_any_of": ["site_plan", "survey", "other"],
        "recommended_file_types": ["site_plan", "survey"],
        "summary": "Upload a site plan, survey, utility sheet, or another site-related document.",
    },
}

BUILTIN_RULE_GROUPS = {
    "zoning": [
        {"rule": "Side setback minimum", "source": "Zoning rules pack"},
        {"rule": "Height limit", "source": "Zoning rules pack"},
        {"rule": "Parking ratio", "source": "Zoning rules pack"},
    ],
    "building": [
        {"rule": "Dual egress requirements", "source": "IBC snippets"},
        {"rule": "Accessibility requirements", "source": "IBC snippets"},
    ],
    "fire": [
        {"rule": "Sprinkler requirements", "source": "IBC snippets"},
    ],
    "site": [
        {"rule": "Flood zone determination", "source": "Environmental triggers"},
        {"rule": "Water/sewer capacity review", "source": "Utility requirements"},
    ],
    "permits": [],
}

MANHATTAN_DISTRICT_TOKENS = {"RL", "RL-A", "RM", "RH", "RC"}


def _project_dir(project_id: str) -> Path:
    path = PROJECT_UPLOAD_ROOT / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _serialize_project(project: Project, cases: list[PermitCase] | None = None) -> dict[str, Any]:
    case_list = cases if cases is not None else list(project.cases or [])
    latest = None
    if case_list:
        latest = max(case_list, key=lambda c: c.created_at or datetime.min.replace(tzinfo=timezone.utc))

    last_status = None
    readiness = None
    if latest and latest.results:
        last_status = latest.status
        readiness = (latest.results.get("case_summary") or {}).get("readiness_score")

    return {
        "id": project.project_id,
        "name": project.name,
        "address": project.address,
        "projectType": project.project_type,
        "jurisdiction": project.jurisdiction,
        "area": project.area,
        "files": [
            {
                "id": f.file_id,
                "name": f.name,
                "type": f.file_type,
                "label": f.document_label,
                "size": f.size,
                "sections": f.file_sections or [],
                "uploadedAt": f.uploaded_at.isoformat() if f.uploaded_at else None,
                "isPrimaryBrief": f.is_primary_brief,
            }
            for f in (project.files or [])
        ],
        "customRules": project.custom_rules or [],
        "moduleRequirements": _module_requirements_payload(list(project.files or [])),
        "analyses": [
            {
                "caseId": c.case_id,
                "status": c.status,
                "createdAt": c.created_at.isoformat() if c.created_at else None,
                "readiness": (c.results or {}).get("case_summary", {}).get("readiness_score"),
            }
            for c in sorted(
                case_list,
                key=lambda c: c.created_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
        ],
        "lastAnalysisStatus": last_status,
        "readinessScore": readiness,
        "createdAt": project.created_at.isoformat() if project.created_at else None,
        "updatedAt": project.updated_at.isoformat() if project.updated_at else None,
    }


async def list_projects() -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project).options(selectinload(Project.files), selectinload(Project.cases))
        )
        projects = result.scalars().all()
        return [_serialize_project(p) for p in projects]


async def get_project(project_id: str) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.files), selectinload(Project.cases))
        )
        project = result.scalar_one_or_none()
        if not project:
            return None
        return _serialize_project(project)


async def create_project(data: dict[str, Any]) -> dict[str, Any]:
    project_id = str(uuid4())
    now = datetime.now(timezone.utc)
    jurisdiction = data.get("jurisdiction", "austin_tx")
    if jurisdiction not in JURISDICTION_PATHS:
        raise HTTPException(status_code=400, detail=f"Unsupported jurisdiction: {jurisdiction}")

    async with SessionLocal() as session:
        project = Project(
            project_id=project_id,
            name=data["name"],
            address=data["address"],
            project_type=data.get("projectType", "multifamily_residential"),
            jurisdiction=jurisdiction,
            area=data.get("area"),
            custom_rules=data.get("customRules", []),
            created_at=now,
            updated_at=now,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project, ["files", "cases"])
        return _serialize_project(project)


async def update_project(project_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.files), selectinload(Project.cases))
        )
        project = result.scalar_one_or_none()
        if not project:
            return None

        if "name" in data:
            project.name = data["name"]
        if "address" in data:
            project.address = data["address"]
        if "projectType" in data:
            project.project_type = data["projectType"]
        if "jurisdiction" in data:
            if data["jurisdiction"] not in JURISDICTION_PATHS:
                raise HTTPException(status_code=400, detail=f"Unsupported jurisdiction: {data['jurisdiction']}")
            project.jurisdiction = data["jurisdiction"]
        if "area" in data:
            project.area = data["area"]
        if "customRules" in data:
            project.custom_rules = data["customRules"]
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return _serialize_project(project)


async def delete_project(project_id: str) -> bool:
    async with SessionLocal() as session:
        result = await session.execute(select(Project).where(Project.project_id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return False
        await session.delete(project)
        await session.commit()

    proj_dir = PROJECT_UPLOAD_ROOT / project_id
    if proj_dir.exists():
        shutil.rmtree(proj_dir, ignore_errors=True)
    return True


async def add_project_file(
    project_id: str,
    file: UploadFile,
    file_type: str | None = None,
    is_primary_brief: bool = False,
    document_label: str | None = None,
    file_sections: str | None = None,
) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.files))
        )
        project = result.scalar_one_or_none()
        if not project:
            return None

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        filename = file.filename or "upload"
        ext = Path(filename).suffix.lower()
        inferred_type = file_type or FILE_TYPE_MAP.get(ext, "other")
        sections = _parse_file_sections(file_sections)
        file_id = str(uuid4())
        dest = _project_dir(project_id) / f"{file_id}_{filename}"
        dest.write_bytes(content)

        if is_primary_brief or inferred_type == "brief_json":
            for f in project.files:
                if f.is_primary_brief:
                    f.is_primary_brief = False

        pf = ProjectFile(
            file_id=file_id,
            project_id=project_id,
            name=filename,
            file_type=inferred_type,
            size=len(content),
            storage_path=str(dest),
            is_primary_brief=is_primary_brief or inferred_type == "brief_json",
            document_label=document_label,
            file_sections=sections,
        )
        session.add(pf)
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return {
            "id": pf.file_id,
            "name": pf.name,
            "type": pf.file_type,
            "label": pf.document_label,
            "size": pf.size,
            "sections": pf.file_sections or [],
            "uploadedAt": pf.uploaded_at.isoformat(),
            "isPrimaryBrief": pf.is_primary_brief,
        }


async def delete_project_file(project_id: str, file_id: str) -> bool:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ProjectFile).where(
                ProjectFile.project_id == project_id,
                ProjectFile.file_id == file_id,
            )
        )
        pf = result.scalar_one_or_none()
        if not pf:
            return False
        path = Path(pf.storage_path)
        if path.is_file():
            path.unlink(missing_ok=True)
        await session.delete(pf)
        await session.commit()
        return True


async def get_project_rules(project_id: str) -> list[dict[str, Any]] | None:
    async with SessionLocal() as session:
        result = await session.execute(select(Project).where(Project.project_id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return None
        return project.custom_rules or []


async def get_project_context(project_id: str) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        result = await session.execute(select(Project).where(Project.project_id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return None
        return {
            "id": project.project_id,
            "name": project.name,
            "address": project.address,
            "projectType": project.project_type,
            "jurisdiction": project.jurisdiction,
            "area": project.area,
            "customRules": project.custom_rules or [],
        }


async def save_project_rules(project_id: str, rules: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    async with SessionLocal() as session:
        result = await session.execute(select(Project).where(Project.project_id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return None
        project.custom_rules = rules
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return rules


def _parse_file_sections(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(v) for v in parsed if str(v).strip()]
    except json.JSONDecodeError:
        pass
    return [part.strip() for part in raw.split(",") if part.strip()]


def _build_brief_from_project(project: Project) -> ProjectBrief:
    return ProjectBrief(
        project_name=project.name,
        address=project.address,
        jurisdiction=project.jurisdiction,
        project_type=ProjectType(project.project_type),
        units=0,
        stories=0,
        gross_sqft=0,
        lot_sqft=0,
        parking_spaces=0,
        notes=f"Area: {project.area}" if project.area else None,
    )


def _module_requirements_payload(files: list[ProjectFile]) -> dict[str, Any]:
    present_types = {f.file_type for f in files}
    file_sections = {section for f in files for section in (f.file_sections or [])}
    payload: dict[str, Any] = {}
    for key, config in ANALYSIS_MODULES.items():
        required_any_of = list(config.get("required_any_of", []))
        recommended_missing = [t for t in config["recommended_file_types"] if t not in present_types]
        has_required_type = any(t in present_types for t in required_any_of)
        has_mapped_files = key in file_sections
        can_run = has_required_type or has_mapped_files
        payload[key] = {
            "label": config["label"],
            "requiredAnyOf": required_any_of,
            "recommendedFileTypes": config["recommended_file_types"],
            "requiredMissing": [] if can_run else required_any_of,
            "recommendedMissing": recommended_missing,
            "canRun": can_run,
            "hasMappedFiles": has_mapped_files,
            "summary": config.get("summary", ""),
        }
    return payload


async def analyze_project(project_id: str, modules: list[str] | None = None) -> dict[str, Any]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.files))
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        brief_file = next((f for f in project.files if f.is_primary_brief), None)
        if not brief_file:
            brief_file = next(
                (f for f in project.files if f.file_type == "brief_json"),
                None,
            )
        path = Path(brief_file.storage_path) if brief_file else None
        project_type = ProjectType(project.project_type)
        jurisdiction = project.jurisdiction
        project_name = project.name
        project_address = project.address
        project_area = project.area
        custom_rules = list(project.custom_rules or [])
        files = list(project.files or [])
        brief_filename = brief_file.name if brief_file else "generated-project-brief.json"
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()

    if path:
        from starlette.datastructures import Headers, UploadFile as StarletteUploadFile

        with path.open("rb") as fh:
            upload = StarletteUploadFile(
                filename=brief_filename,
                file=fh,
                headers=Headers({"content-type": "application/octet-stream"}),
            )
            brief, _ = await parse_intake_upload(upload, project_type)
        brief.jurisdiction = jurisdiction
        brief.project_name = project_name
        brief.address = project_address
    else:
        brief = _build_brief_from_project(project)

    if project_area:
        brief.notes = f"{brief.notes or ''}\nArea: {project_area}".strip()

    selected_modules = [m for m in (modules or list(ANALYSIS_MODULES.keys())) if m in ANALYSIS_MODULES]
    requirements = _module_requirements_payload(files)
    blocked_modules = [requirements[m]["label"] for m in selected_modules if not requirements[m]["canRun"]]
    if blocked_modules:
        raise HTTPException(
            status_code=400,
            detail=(
                "Upload at least one relevant file before running "
                + ", ".join(blocked_modules)
                + " analysis."
            ),
        )
    if not selected_modules:
        raise HTTPException(status_code=400, detail="No runnable analysis modules selected.")
    return await start_case_async(
        brief,
        project_id=project_id,
        custom_rules=custom_rules,
        selected_modules=selected_modules,
        module_requirements=requirements,
    )


async def suggest_rules(project_id: str) -> list[dict[str, Any]]:
    """Use the LLM to suggest custom rules based on project metadata and jurisdiction."""
    import json
    from uuid import uuid4

    async with SessionLocal() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        context = {
            "name": project.name,
            "address": project.address,
            "project_type": project.project_type,
            "jurisdiction": project.jurisdiction,
        }

    from shared.agent_logic.local_runner import _make_llm, _skip_llm

    fallback = [
        {
            "category": "building",
            "rule": "Maximum building height compliance",
            "condition": "Building height must not exceed the district maximum.",
            "severity": "blocker",
        },
        {
            "category": "zoning",
            "rule": "Minimum parking ratio",
            "condition": "Parking spaces must meet the per-unit minimum for the project type.",
            "severity": "warning",
        },
        {
            "category": "site",
            "rule": "Impervious cover limit",
            "condition": "Impervious surface coverage must stay within the allowed percentage.",
            "severity": "warning",
        },
    ]

    def with_ids(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "id": str(uuid4()),
                "category": r.get("category", "custom"),
                "rule": r.get("rule", "Suggested rule"),
                "condition": r.get("condition", ""),
                "severity": r.get("severity", "warning"),
                "enabled": True,
            }
            for r in rules
        ]

    if _skip_llm():
        return with_ids(fallback)

    from langchain_core.messages import HumanMessage

    prompt = (
        "You are a permitting expert. Suggest 4-6 relevant compliance rules to check for this "
        "real estate project. Return ONLY a JSON array of objects with keys: "
        '"category" (one of zoning, building, site, environmental, custom), "rule" (short title), '
        '"condition" (what to verify), "severity" (blocker, warning, or info).\n\n'
        f"Project context:\n{json.dumps(context, indent=2)}"
    )

    try:
        llm = _make_llm()
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        text = (resp.content or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        if not isinstance(parsed, list) or not parsed:
            return with_ids(fallback)
        return with_ids(parsed)
    except Exception:
        return with_ids(fallback)


async def get_builtin_rules(jurisdiction: str) -> list[dict[str, str]]:
    """Return read-only summary of built-in checks for a jurisdiction."""
    from shared.tools.knowledge import jurisdiction_context, load_json

    with jurisdiction_context(jurisdiction):
        rules: list[dict[str, str]] = []
        for group, items in BUILTIN_RULE_GROUPS.items():
            for item in items:
                rules.append({**item, "category": group, "group": group})
        try:
            catalog = load_json("permit_catalog.json", jurisdiction)
            for p in (catalog.get("permits") or catalog.get("permit_types") or [])[:3]:
                rules.append(
                    {
                        "category": "permits",
                        "group": "permits",
                        "rule": p.get("name", p.get("permit_name", "Permit")),
                        "source": "Permit catalog",
                    }
                )
        except Exception:
            pass
        return rules


async def get_builtin_rules_for_project(
    jurisdiction: str,
    *,
    area: str | None = None,
    project_type: str | None = None,
) -> list[dict[str, str]]:
    if jurisdiction != "manhattan_ks":
        return await get_builtin_rules(jurisdiction)

    with jurisdiction_context(jurisdiction):
        return _build_manhattan_rule_library(area=area, project_type=project_type)


def _build_manhattan_rule_library(
    *,
    area: str | None = None,
    project_type: str | None = None,
) -> list[dict[str, str]]:
    rules: list[dict[str, str]] = []
    area_token = (area or "").strip().upper()

    zoning = load_json("zoning_rules.json", "manhattan_ks")
    for district, details in (zoning.get("residential_districts") or {}).items():
        if area_token and district.upper() != area_token:
            continue
        rules.append(
            {
                "category": "zoning",
                "group": "zoning",
                "rule": f"{district}: district standards",
                "source": details.get("citation", "MDC residential district table"),
            }
        )
        for housing_type, housing in (details.get("housing_types") or {}).items():
            if "max_height_ft" in housing:
                rules.append(
                    {
                        "category": "zoning",
                        "group": "zoning",
                        "rule": f"{district} {housing_type}: max height {housing['max_height_ft']} ft",
                        "source": details.get("citation", "MDC district table"),
                    }
                )
            if "setbacks_ft" in housing:
                rules.append(
                    {
                        "category": "zoning",
                        "group": "zoning",
                        "rule": f"{district} {housing_type}: setback standards",
                        "source": details.get("citation", "MDC district table"),
                    }
                )
            if "max_building_coverage_pct" in housing:
                rules.append(
                    {
                        "category": "zoning",
                        "group": "zoning",
                        "rule": f"{district} {housing_type}: max building coverage {housing['max_building_coverage_pct']}%",
                        "source": details.get("citation", "MDC district table"),
                    }
                )

    if not area_token and zoning.get("infill_development"):
        rules.append(
            {
                "category": "zoning",
                "group": "zoning",
                "rule": "Infill development standards",
                "source": zoning["infill_development"].get("citation", "MDC infill development"),
            }
        )

    site = load_json("site_development_rules.json", "manhattan_ks")
    for label, source in [
        ("Fence and wall standards", site.get("fences", {}).get("front_and_street_side", {}).get("citation")),
        ("Accessory structure setbacks", site.get("accessory_structures", {}).get("citation")),
        ("Clear vision triangle", site.get("clear_vision_triangle", {}).get("citation")),
        ("Parking standards", site.get("parking", {}).get("citation")),
        ("Landscaping and buffering", site.get("landscaping_and_buffering", {}).get("citation")),
        ("Solid waste enclosure", site.get("solid_waste_enclosure", {}).get("citation")),
    ]:
        rules.append({"category": "site", "group": "site", "rule": label, "source": source or "MDC Article 26-7"})

    env = load_json("environmental_triggers.json", "manhattan_ks")
    for trigger in env.get("triggers", []):
        rules.append(
            {
                "category": "site",
                "group": "site",
                "rule": trigger.get("action", trigger.get("id", "Environmental trigger")),
                "source": trigger.get("citation", "Environmental triggers"),
            }
        )

    utilities = load_json("utility_requirements.json", "manhattan_ks")
    for requirement in utilities.get("requirements", []):
        rules.append(
            {
                "category": "site",
                "group": "site",
                "rule": requirement.get("action", requirement.get("id", "Utility requirement")),
                "source": requirement.get("citation", "Utility requirements"),
            }
        )

    snippets = load_json("building_code_snippets/snippets.json", "manhattan_ks")
    for snippet in snippets.get("snippets", []):
        group = "fire" if snippet.get("topic") == "fire" else "building"
        rules.append(
            {
                "category": group,
                "group": group,
                "rule": snippet.get("text", "")[:140],
                "source": snippet.get("citation", "Building code snippet"),
            }
        )

    catalog = load_json("permit_catalog.json", "manhattan_ks")
    for permit in catalog.get("permits", []):
        rules.append(
            {
                "category": "permits",
                "group": "permits",
                "rule": permit.get("permit_name", permit.get("id", "Permit")),
                "source": permit.get("citation", "Permit catalog"),
            }
        )

    chunks_payload = load_json("code_chunks/chunks.json", "manhattan_ks")
    for chunk in chunks_payload.get("chunks", []):
        if not _chunk_matches_area(chunk, area_token):
            continue
        group = _group_for_chunk(chunk)
        if project_type and not _chunk_matches_project_type(chunk, project_type):
            if group not in {"permits", "building", "site"}:
                continue
        rules.append(
            {
                "category": group,
                "group": group,
                "rule": f"{chunk.get('section')}: {chunk.get('title')}",
                "source": chunk.get("source_url", "MDC Chapter 26"),
            }
        )

    return _dedupe_builtin_rules(rules)


def _chunk_matches_area(chunk: dict[str, Any], area_token: str) -> bool:
    if not area_token:
        return True
    if area_token not in MANHATTAN_DISTRICT_TOKENS:
        return True
    haystack = f"{chunk.get('title', '')} {chunk.get('text', '')}"
    if re.search(rf"\b{re.escape(area_token)}\b", haystack):
        return True
    general_articles = {"26-7", "26-8", "26-9", "26-10"}
    return chunk.get("article") in general_articles


def _chunk_matches_project_type(chunk: dict[str, Any], project_type: str) -> bool:
    tags = set(chunk.get("tags") or [])
    if project_type in {"multifamily_residential", "mixed_use"}:
        return "multifamily" in tags or "commercial" in tags or "general" in tags or not tags
    if project_type in {"commercial", "commercial_tenant_improvement", "industrial"}:
        return "commercial" in tags or "building" in tags or "procedure" in tags or not tags
    return True


def _group_for_chunk(chunk: dict[str, Any]) -> str:
    tags = set(chunk.get("tags") or [])
    article = str(chunk.get("article", ""))
    if "procedure" in tags or article in {"26-8", "26-9"}:
        return "permits"
    if "building" in tags:
        return "building"
    if "flood" in tags or "environmental" in tags or "utility" in tags or "access" in tags:
        return "site"
    if "parking" in tags or "fence" in tags or "design" in tags or "subdivision" in tags:
        return "site"
    return "zoning"


def _dedupe_builtin_rules(rules: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for rule in rules:
        key = (rule.get("group", ""), rule.get("rule", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(rule)
    return out
