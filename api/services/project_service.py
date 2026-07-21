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

from api.models import PermitCase, Project, ProjectFile, ProjectPermit
from api.services.case_service import SessionLocal, start_case_async
from api.services.document_classifier import DOCUMENT_TYPES, classify_project_document
from api.services.kcmo_zoning_rules import build_kcmo_rules
from api.services.manhattan_zoning_rules import build_manhattan_rules
from api.services.zoning_service import (
    JURISDICTION_ZONING,
    has_zoning_rule_coverage,
    public_zoning_source_url,
    resolve_zoning,
)
from shared.schemas.project_brief import ProjectBrief, ProjectType
from shared.tools.kcmo_approvals import build_kcmo_approval_recommendations
from shared.tools.kcmo_permits import match_kcmo_applications, rule_family_for_category
from shared.tools.kck_permits import match_kck_applications
from shared.tools.knowledge import JURISDICTION_PATHS, jurisdiction_context, load_json

PROJECT_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "projects"

USER_MANAGED_REQUIREMENT_STATUSES = {"removed_by_user", "manual"}
DEFAULT_SCOPE = {
    "new_construction": False,
    "addition": False,
    "alteration": False,
    "repair": False,
    "demolition": False,
    "structural_work": False,
    "electrical_work": False,
    "plumbing_work": False,
    "mechanical_hvac_work": False,
    "fire_alarm_sprinkler_work": False,
    "signs": False,
    "change_use_occupancy": False,
    "grading_land_disturbance": False,
    "driveway_sidewalk_row": False,
    "solar_battery_generator_ev": False,
    "water_sewer_connections": False,
}

ANALYSIS_MODULES = {
    "zoning": {
        "label": "Zoning",
        "required_any_of": ["site_plan", "civil_plan", "survey", "code_analysis", "supporting_document", "other"],
        "recommended_file_types": ["site_plan", "survey", "code_analysis"],
        "summary": "Upload a site plan, survey, zoning memo, or another zoning-related document.",
    },
    "building": {
        "label": "Building",
        "required_any_of": ["architectural_plan", "structural_plan", "elevation", "code_analysis", "supporting_document", "other"],
        "recommended_file_types": ["architectural_plan", "structural_plan", "elevation", "code_analysis"],
        "summary": "Upload a floor plan, elevations, code analysis, or another building package document.",
    },
    "fire": {
        "label": "Fire / Life Safety",
        "required_any_of": ["fire_protection_plan", "architectural_plan", "supporting_document", "other"],
        "recommended_file_types": ["fire_protection_plan", "architectural_plan"],
        "summary": "Upload a fire/life-safety plan, floor plan, or another fire review document.",
    },
    "site": {
        "label": "Site / Utilities",
        "required_any_of": ["site_plan", "civil_plan", "survey", "supporting_document", "other"],
        "recommended_file_types": ["site_plan", "civil_plan", "survey"],
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

KCMO_PERMIT_RULE_CATEGORIES = {
    "commercial_building": "building",
    "residential_building": "building",
    "electrical": "building",
    "mechanical": "building",
    "plumbing": "building",
    "demolition": "building",
    "fire_protection": "fire",
    "certificate_of_occupancy": "building",
    "signs": "zoning",
    "zoning": "zoning",
    "street_and_row": "site",
    "major_infrastructure": "site",
    "water_service": "site",
}

KCMO_PERMIT_TYPE_ALIASES = {
    "zoning": [
        "zoning_verification",
        "certificate_appropriateness",
        "ur_development_plan",
        "platting_lot_consolidation",
    ],
    "commercial_building": [
        "commercial_building",
        "foundation_early_start",
        "shoring_excavation_support",
        "retaining_wall",
        "elevator_state",
        "boiler_pressure_vessel_state",
    ],
    "electrical": ["electrical", "electrical_service"],
    "mechanical": ["mechanical"],
    "plumbing": ["plumbing", "gas_piping", "backflow_prevention"],
    "fire_protection": [
        "fire_sprinkler",
        "fire_alarm",
        "standpipe",
        "fire_pump",
        "errc_bda_das",
        "smoke_control",
        "kitchen_hood_suppression",
        "hazardous_materials_operational",
    ],
    "demolition": ["demolition", "asbestos_neshap"],
    "signs": ["sign"],
    "street_and_row": [
        "right_of_way",
        "row_excavation",
        "sidewalk_curb_driveway",
        "traffic_lane_sidewalk_closure",
        "streetcar_track_access",
        "encroachment_vault",
        "hauling_oversize",
        "crane_erection",
    ],
    "major_infrastructure": [
        "land_disturbance",
        "modnr_construction_stormwater",
        "stormwater_management",
        "dust_control",
    ],
    "water_service": [
        "domestic_water_service",
        "fire_water_service",
        "sanitary_sewer_connection",
        "storm_sewer_connection",
        "water_main_extension",
        "industrial_pretreatment",
    ],
    "certificate_of_occupancy": ["temporary_certificate_occupancy", "certificate_of_occupancy"],
}

KCMO_RULE_EXACT_TARGETS = {
    "commercial_building": [
        ["compass_permit_618"],
        ["compass_permit_567"],
        ["compass_permit_587"],
        ["compass_permit_567", "compass_permit_587", "compass_permit_618"],
    ],
    "electrical": [
        ["compass_permit_576"],
        ["compass_permit_583", "compass_permit_767"],
        ["compass_permit_576", "compass_permit_583", "compass_permit_767"],
        ["compass_permit_576", "compass_permit_583", "compass_permit_767"],
        ["compass_permit_576", "compass_permit_583", "compass_permit_767"],
        ["compass_permit_576", "compass_permit_583", "compass_permit_767"],
        ["compass_permit_576", "compass_permit_583", "compass_permit_767"],
        ["compass_permit_583", "compass_permit_767"],
        ["compass_permit_434"],
        ["compass_permit_430", "compass_permit_431"],
        ["compass_permit_772"],
        ["compass_permit_432"],
        ["compass_permit_576", "compass_permit_583", "compass_permit_767", "compass_permit_434", "compass_permit_430", "compass_permit_431", "compass_permit_772", "compass_permit_432"],
    ],
    "fire_protection": [
        ["compass_permit_435", "compass_permit_436"],
        ["compass_permit_592", "compass_permit_591"],
        ["compass_permit_435", "compass_permit_436", "compass_permit_592", "compass_permit_591", "compass_plan_652"],
    ],
    "mechanical": [
        ["compass_permit_584", "compass_permit_585", "compass_permit_768"],
        ["compass_permit_584"],
        ["compass_permit_438"],
        ["compass_permit_439", "compass_permit_440"],
    ],
    "plumbing": [
        ["compass_permit_608", "compass_permit_609", "compass_permit_769"],
        ["compass_permit_608"],
        ["compass_permit_445"],
        ["compass_permit_442", "compass_permit_443", "compass_permit_873", "compass_permit_441"],
        ["compass_permit_608", "compass_permit_609", "compass_permit_769", "compass_permit_445"],
    ],
    "residential_building": [
        ["compass_permit_566", "compass_permit_589", "compass_permit_590"],
        ["compass_permit_446", "compass_permit_573", "compass_permit_588", "compass_permit_566", "compass_permit_589", "compass_permit_590"],
        ["compass_permit_446", "compass_permit_573", "compass_permit_588", "compass_permit_566", "compass_permit_589", "compass_permit_590"],
        ["compass_permit_573"],
        ["compass_permit_446"],
        ["compass_permit_588"],
    ],
    "certificate_of_occupancy": [
        ["certificate_of_occupancy"],
        ["certificate_of_occupancy"],
        ["certificate_of_occupancy"],
        ["certificate_of_occupancy"],
        ["certificate_of_occupancy"],
    ],
}

KCMO_EXEMPTION_EXACT_TARGETS = {
    "electrical": [
        ["compass_permit_576", "compass_permit_583", "compass_permit_767", "compass_permit_434", "compass_permit_430", "compass_permit_431", "compass_permit_772", "compass_permit_432"],
        ["compass_permit_576", "compass_permit_583", "compass_permit_767", "compass_permit_434", "compass_permit_430", "compass_permit_431", "compass_permit_772", "compass_permit_432"],
        ["compass_permit_576", "compass_permit_583", "compass_permit_767", "compass_permit_434", "compass_permit_430", "compass_permit_431", "compass_permit_772", "compass_permit_432"],
        ["compass_permit_576", "compass_permit_583", "compass_permit_767", "compass_permit_434", "compass_permit_430", "compass_permit_431", "compass_permit_772", "compass_permit_432"],
        ["compass_permit_432"],
    ],
}

KCMO_GENERIC_RULE_INDICES = {
    "commercial_building": {1, 4},
    "electrical": {3, 4, 5, 6, 7, 13},
    "fire_protection": {3},
    "mechanical": {1, 2},
    "plumbing": {1, 2, 5},
    "certificate_of_occupancy": {1, 2, 3, 4, 5},
}

KCMO_GENERIC_EXEMPTION_INDICES = {
    "electrical": {1, 2, 3, 4},
}

KCMO_COMMERCIAL_RULE_OVERRIDES = {
    ("electrical", 3): "Any commercial electrical service of 400 amps or larger requires the completed IB160 submission identified by CompassKC.",
    ("electrical", 4): "Service equipment rated 800 through 1199 amps requires a sealed one-line drawing plan case under IB160.",
    ("electrical", 6): "Transformers, generators, battery systems, fire pumps, wind turbines, and automatic transfer switches require the IB160 plan or one-line-drawing path.",
    ("mechanical", 1): "Use Mechanical General - Commercial for general mechanical work in commercial and multifamily buildings.",
    ("plumbing", 1): "Use Plumbing General - Commercial for general plumbing work in commercial and multifamily buildings.",
    ("plumbing", 4): "Commercial gas test or reconnect work uses its separate commercial application route.",
    ("demolition", 1): "Commercial demolition work has separate complete, interior, partial, and pre-demolition-inspection application routes.",
}

KCMO_RESIDENTIAL_EXACT_TYPES = {
    "compass_permit_583", "compass_permit_767", "compass_permit_434",
    "compass_permit_431", "compass_permit_432", "compass_permit_436",
    "compass_permit_591", "compass_permit_585", "compass_permit_768",
    "compass_permit_438", "compass_permit_439", "compass_permit_440",
    "compass_permit_609", "compass_permit_769", "compass_permit_445",
    "compass_permit_443", "compass_permit_873", "compass_permit_441",
    "compass_permit_446", "compass_permit_573", "compass_permit_588",
    "compass_permit_566", "compass_permit_589", "compass_permit_590",
}

KCK_APPLICATION_GENERIC_ALIASES = {
    "residential_building": ["building_permit"],
    "commercial_building_non_drc": ["building_permit"],
    "commercial_building_drc": ["building_permit"],
    "commercial_building_drc_floodplain": ["building_permit"],
    "phased_building_approval": ["building_permit"],
    "electrical": ["electrical"],
    "temporary_electrical": ["electrical"],
    "mechanical": ["mechanical"],
    "plumbing": ["plumbing"],
    "gas_pressure_test": ["plumbing"],
    "demolition": ["demolition"],
    "certificate_of_occupancy": ["certificate_of_occupancy"],
    "sign_incidental": ["sign"],
    "sign_flag": ["sign"],
    "sign_attached": ["sign"],
    "sign_detached": ["sign"],
    "billboard_under_300": ["sign"],
    "billboard_300_or_more": ["sign"],
    "land_disturbance": ["land_disturbance"],
    "right_of_way": ["right_of_way"],
    "street_excavation": ["right_of_way"],
    "driveway": ["right_of_way"],
    "sidewalk_curb": ["right_of_way"],
    "street_closure": ["right_of_way"],
    "dumpster_row": ["right_of_way"],
    "hauling": ["right_of_way"],
    "sanitary_sewer_tap": ["utility_service"],
    "sewer_line_row": ["utility_service"],
    "sewer_abandonment": ["utility_service"],
    "bpu_water_service": ["utility_service"],
    "bpu_electric_service": ["utility_service"],
    "bpu_disconnect": ["utility_service"],
    "bpu_temporary_service": ["utility_service"],
    "fire_sprinkler": ["fire_protection"],
    "fire_alarm": ["fire_protection"],
    "commercial_cooking_suppression": ["fire_protection"],
}

MANHATTAN_DISTRICT_TOKENS = {
    "BC", "BP", "CA", "CC", "CD", "CN", "ICS", "IG", "IL", "LR",
    "MX", "PI-1", "PI-2", "PUD", "RC", "RH", "RL", "RL-A", "RM", "UC",
}
LEGACY_RULE_PLACEHOLDERS = (
    "enter the value",
    "enter the spaces",
    "enter the exact threshold",
    "cannot be selected until area",
    "numeric side-setback minimum for district",
    "numeric height limit for district",
)


def _usable_custom_rules(rules: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [
        rule
        for rule in (rules or [])
        if not any(phrase in str(rule.get("condition", "")).casefold() for phrase in LEGACY_RULE_PLACEHOLDERS)
    ]


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

    zoning_profile = dict(project.zoning_profile or {})
    public_source_url = public_zoning_source_url(project.jurisdiction, project.address)
    if public_source_url:
        zoning_profile["sourceUrl"] = public_source_url
    zoning_warnings = list(project.zoning_warnings or [])
    if has_zoning_rule_coverage(project.jurisdiction, project.area):
        zoning_warnings = [warning for warning in zoning_warnings if warning.get("code") != "numeric_rules_missing"]
    zoning_rules: list[dict[str, Any]] = []
    if project.jurisdiction == "kansas_city_mo":
        zoning_rules = build_kcmo_rules(project.area, zoning_profile, project.project_type)
    elif project.jurisdiction == "manhattan_ks":
        zoning_rules = build_manhattan_rules(project.area, zoning_profile)

    return {
        "id": project.project_id,
        "name": project.name,
        "address": project.address,
        "projectType": project.project_type,
        "jurisdiction": project.jurisdiction,
        "area": project.area,
        "zoningStatus": project.zoning_status or "pending",
        "zoningProfile": zoning_profile,
        "zoningWarnings": zoning_warnings,
        "zoningRules": zoning_rules,
        "scope": _normalized_scope(project.scope),
        "permitAnswers": dict(project.permit_answers or {}),
        "files": [
            {
                "id": f.file_id,
                "name": f.name,
                "type": f.file_type,
                "label": f.document_label,
                "size": f.size,
                "uploadedAt": f.uploaded_at.isoformat() if f.uploaded_at else None,
                "aiSummary": f.ai_summary,
                "classificationSource": f.classification_source or "legacy",
                "permitTypes": f.permit_types or [],
            }
            for f in (project.files or [])
        ],
        "permits": [_serialize_project_permit(p) for p in sorted(
            project.permits or [],
            key=lambda p: (
                (p.recommendation_evidence or {}).get("catalogRule", {}).get("sequence", 999),
                p.permit_name,
            ),
        )],
        "customRules": _usable_custom_rules(project.custom_rules),
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
            select(Project).options(selectinload(Project.files), selectinload(Project.cases), selectinload(Project.permits))
        )
        projects = result.scalars().all()
        for project in projects:
            _sync_project_permit_recommendations(project)
        await session.commit()
        return [_serialize_project(p) for p in projects]


async def get_project(project_id: str) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.files), selectinload(Project.cases), selectinload(Project.permits))
        )
        project = result.scalar_one_or_none()
        if not project:
            return None
        if not project.zoning_profile or (
            project.jurisdiction == "kansas_city_mo"
            and (project.zoning_profile or {}).get("permitContext", {}).get("version") != 1
        ):
            await _resolve_project_zoning(project)
        _sync_project_permit_recommendations(project)
        await session.commit()
        return _serialize_project(project)


async def create_project(data: dict[str, Any]) -> dict[str, Any]:
    project_id = str(uuid4())
    now = datetime.now(timezone.utc)
    jurisdiction = data.get("jurisdiction", "kansas_city_mo")
    if jurisdiction not in JURISDICTION_ZONING:
        raise HTTPException(status_code=400, detail=f"Unsupported jurisdiction: {jurisdiction}")
    _validate_jurisdiction_address(jurisdiction, data["address"])
    resolution = await resolve_zoning(data["address"], jurisdiction)

    async with SessionLocal() as session:
        project = Project(
            project_id=project_id,
            name=data["name"],
            address=data["address"],
            project_type=data.get("projectType", "multifamily_residential"),
            jurisdiction=jurisdiction,
            area=(resolution.get("profile") or {}).get("district"),
            zoning_status=resolution["status"],
            zoning_profile=resolution.get("profile") or {},
            zoning_warnings=resolution.get("warnings") or [],
            scope=_normalized_scope(data.get("scope")),
            permit_answers=data.get("permitAnswers", {}),
            custom_rules=data.get("customRules", []),
            permits=[],
            created_at=now,
            updated_at=now,
        )
        session.add(project)
        await session.flush()
        _sync_project_permit_recommendations(project)
        await session.commit()
        await session.refresh(project, ["files", "cases"])
        await session.refresh(project, ["permits"])
        return _serialize_project(project)


async def update_project(project_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.files), selectinload(Project.cases), selectinload(Project.permits))
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
            if data["jurisdiction"] not in JURISDICTION_ZONING:
                raise HTTPException(status_code=400, detail=f"Unsupported jurisdiction: {data['jurisdiction']}")
            project.jurisdiction = data["jurisdiction"]
        address_context_changed = "address" in data or "jurisdiction" in data
        if address_context_changed:
            await _resolve_project_zoning(project)
        if "scope" in data:
            project.scope = _normalized_scope(data["scope"])
        if "permitAnswers" in data:
            project.permit_answers = dict(data["permitAnswers"] or {})
        if "customRules" in data:
            project.custom_rules = data["customRules"]
        project.updated_at = datetime.now(timezone.utc)
        _sync_project_permit_recommendations(project)
        await session.commit()
        await session.refresh(project, ["files", "cases", "permits"])
        return _serialize_project(project)


async def refresh_project_zoning(project_id: str) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.files), selectinload(Project.cases), selectinload(Project.permits))
        )
        project = result.scalar_one_or_none()
        if not project:
            return None
        await _resolve_project_zoning(project)
        _sync_project_permit_recommendations(project)
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(project, ["files", "cases", "permits"])
        return _serialize_project(project)


async def _resolve_project_zoning(project: Project) -> None:
    _validate_jurisdiction_address(project.jurisdiction, project.address)
    resolution = await resolve_zoning(project.address, project.jurisdiction)
    project.zoning_status = resolution["status"]
    project.zoning_profile = resolution.get("profile") or {}
    project.zoning_warnings = resolution.get("warnings") or []
    project.area = project.zoning_profile.get("district")


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
    document_label: str | None = None,
) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.files), selectinload(Project.permits))
        )
        project = result.scalar_one_or_none()
        if not project:
            return None

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        filename = file.filename or "upload"
        if file_type and file_type not in DOCUMENT_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported document type.")
        classification = await classify_project_document(
            filename=filename,
            content=content,
            content_type=file.content_type,
            permits=[
                {"permit_type": permit.permit_type, "permit_name": permit.permit_name}
                for permit in (project.permits or [])
                if permit.requirement_status != "not_required"
            ],
        )
        inferred_type = file_type or classification["document_type"]
        file_id = str(uuid4())
        dest = _project_dir(project_id) / f"{file_id}_{filename}"
        dest.write_bytes(content)

        pf = ProjectFile(
            file_id=file_id,
            project_id=project_id,
            name=filename,
            file_type=inferred_type,
            size=len(content),
            storage_path=str(dest),
            document_label=document_label,
            ai_summary=classification["summary"],
            classification_source="user" if file_type else classification["source"],
            permit_types=classification["permit_types"],
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
            "uploadedAt": pf.uploaded_at.isoformat(),
            "aiSummary": pf.ai_summary,
            "classificationSource": pf.classification_source,
            "permitTypes": pf.permit_types or [],
        }


async def update_project_file_type(
    project_id: str,
    file_id: str,
    file_type: str,
) -> dict[str, Any] | None:
    if file_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported document type.")
    async with SessionLocal() as session:
        result = await session.execute(
            select(ProjectFile).where(
                ProjectFile.project_id == project_id,
                ProjectFile.file_id == file_id,
            )
        )
        project_file = result.scalar_one_or_none()
        if not project_file:
            return None
        project_file.file_type = file_type
        project_file.classification_source = "user"
        await session.commit()
        return {
            "id": project_file.file_id,
            "type": project_file.file_type,
            "classificationSource": project_file.classification_source,
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
        return _usable_custom_rules(project.custom_rules)


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


async def list_project_permits(project_id: str) -> list[dict[str, Any]] | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.permits))
        )
        project = result.scalar_one_or_none()
        if not project:
            return None
        _sync_project_permit_recommendations(project)
        await session.commit()
        return [_serialize_project_permit(p) for p in sorted(project.permits or [], key=lambda p: p.permit_name)]


async def add_project_permit(project_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        project = await session.get(Project, project_id)
        if not project:
            return None
        now = datetime.now(timezone.utc)
        permit = ProjectPermit(
            permit_id=str(uuid4()),
            project_id=project_id,
            permit_type=data.get("permitType") or data.get("permit_type") or f"manual_{uuid4().hex[:8]}",
            permit_name=data.get("permitName") or data.get("permit_name") or "Manual permit",
            issuing_authority=data.get("issuingAuthority") or data.get("issuing_authority") or "",
            jurisdiction=data.get("jurisdiction") or project.jurisdiction,
            requirement_status=data.get("requirementStatus") or "manual",
            lifecycle_status=data.get("lifecycleStatus") or "not_started",
            origin="manual",
            reason=data.get("reason") or "Manually added by user.",
            source=data.get("source"),
            portal_url=data.get("portalUrl"),
            coverage_status=data.get("coverageStatus") or "manual",
            dependencies=data.get("dependencies") or [],
            required_documents=data.get("requiredDocuments") or [],
            assigned_employee=data.get("assignedEmployee"),
            assigned_contractor=data.get("assignedContractor"),
            current_blocker=data.get("currentBlocker"),
            next_action=data.get("nextAction") or "Confirm requirements and collect documents.",
            created_at=now,
            updated_at=now,
        )
        session.add(permit)
        project.updated_at = now
        await session.commit()
        return _serialize_project_permit(permit)


async def update_project_permit(project_id: str, permit_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ProjectPermit).where(
                ProjectPermit.project_id == project_id,
                ProjectPermit.permit_id == permit_id,
            )
        )
        permit = result.scalar_one_or_none()
        if not permit:
            return None

        mapping = {
            "permitName": "permit_name",
            "issuingAuthority": "issuing_authority",
            "requirementStatus": "requirement_status",
            "lifecycleStatus": "lifecycle_status",
            "reason": "reason",
            "source": "source",
            "portalUrl": "portal_url",
            "coverageStatus": "coverage_status",
            "parentPermitId": "parent_permit_id",
            "dependencies": "dependencies",
            "requiredDocuments": "required_documents",
            "assignedEmployee": "assigned_employee",
            "assignedContractor": "assigned_contractor",
            "estimatedFeeUsd": "estimated_fee_usd",
            "actualFeeUsd": "actual_fee_usd",
            "applicationNumber": "application_number",
            "issuedNumber": "issued_number",
            "currentBlocker": "current_blocker",
            "nextAction": "next_action",
        }
        for incoming, attr in mapping.items():
            if incoming in data:
                setattr(permit, attr, data[incoming])
        if "requirementStatus" in data:
            permit.origin = "manual"
        permit.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return _serialize_project_permit(permit)


def _normalized_scope(raw: dict[str, Any] | None) -> dict[str, bool]:
    scope = dict(DEFAULT_SCOPE)
    if isinstance(raw, dict):
        for key in scope:
            scope[key] = bool(raw.get(key))
    return scope


def _validate_jurisdiction_address(jurisdiction: str, address: str) -> None:
    normalized = address.lower()
    if jurisdiction == "kansas_city_mo" and (
        "kansas city, ks" in normalized
        or "kansas city ks" in normalized
        or ", ks" in normalized
        or re.search(r",\s*kansas(?:\s+\d{5}(?:-\d{4})?)?\s*$", normalized)
        or normalized.endswith(" ks")
        or normalized.endswith(", kansas")
    ):
        raise HTTPException(
            status_code=400,
            detail="Kansas City, Kansas addresses cannot be evaluated with Kansas City, Missouri rules.",
        )
    if jurisdiction == "kansas_city_ks" and (
        "kansas city, mo" in normalized
        or "kansas city mo" in normalized
        or ", mo" in normalized
        or re.search(r",\s*missouri(?:\s+\d{5}(?:-\d{4})?)?\s*$", normalized)
        or normalized.endswith(" mo")
    ):
        raise HTTPException(
            status_code=400,
            detail="Kansas City, Missouri addresses cannot be evaluated with Kansas City, Kansas rules.",
        )


def _serialize_project_permit(permit: ProjectPermit) -> dict[str, Any]:
    return {
        "id": permit.permit_id,
        "projectId": permit.project_id,
        "permitType": permit.permit_type,
        "permitName": permit.permit_name,
        "issuingAuthority": permit.issuing_authority,
        "jurisdiction": permit.jurisdiction,
        "requirementStatus": permit.requirement_status,
        "lifecycleStatus": permit.lifecycle_status,
        "origin": permit.origin,
        "reason": permit.reason,
        "recommendationEvidence": permit.recommendation_evidence or {},
        "source": permit.source,
        "portalUrl": permit.portal_url,
        "coverageStatus": permit.coverage_status,
        "parentPermitId": permit.parent_permit_id,
        "dependencies": permit.dependencies or [],
        "requiredDocuments": permit.required_documents or [],
        "missingDocumentCount": len(permit.required_documents or []),
        "assignedEmployee": permit.assigned_employee,
        "assignedContractor": permit.assigned_contractor,
        "estimatedFeeUsd": permit.estimated_fee_usd,
        "actualFeeUsd": permit.actual_fee_usd,
        "applicationNumber": permit.application_number,
        "issuedNumber": permit.issued_number,
        "applicationDate": permit.application_date.isoformat() if permit.application_date else None,
        "issuanceDate": permit.issuance_date.isoformat() if permit.issuance_date else None,
        "expirationDate": permit.expiration_date.isoformat() if permit.expiration_date else None,
        "currentBlocker": permit.current_blocker,
        "nextAction": permit.next_action,
        "createdAt": permit.created_at.isoformat() if permit.created_at else None,
        "updatedAt": permit.updated_at.isoformat() if permit.updated_at else None,
    }


def _candidate_permit_recommendations(project: Project) -> list[dict[str, Any]]:
    if project.zoning_status == "invalid_address":
        return []
    if project.jurisdiction not in JURISDICTION_PATHS:
        return []

    scope = _normalized_scope(project.scope)
    if project.jurisdiction == "kansas_city_mo":
        return build_kcmo_approval_recommendations(project, scope)

    try:
        catalog = load_json("permit_catalog.json", project.jurisdiction)
    except Exception:
        return []

    try:
        document_requirements = load_json("document_requirements.json", project.jurisdiction)
    except Exception:
        document_requirements = {}

    development_type = project.project_type
    development_type_candidates = _development_type_candidates(development_type)
    recommendations: list[dict[str, Any]] = []

    for permit in catalog.get("permit_types", []):
        supported = set(permit.get("supported_development_types") or [])
        if supported and not development_type_candidates.intersection(supported):
            continue

        applies_when = list(permit.get("applies_when_any") or permit.get("applies_when") or [])
        default_for = set(permit.get("default_for_development_types") or [])
        active_triggers = _scope_aliases_for(scope)
        triggered_by = [key for key in applies_when if scope.get(key) or key in active_triggers]
        default_match = bool(development_type_candidates.intersection(default_for))
        development_match = bool(development_type_candidates.intersection(applies_when))

        if not triggered_by and not default_match and not development_match:
            continue

        classification = "required" if triggered_by or development_match else "likely_required"
        reason_parts = []
        if triggered_by:
            reason_parts.append("confirmed scope: " + ", ".join(_humanize_scope_key(k) for k in triggered_by))
        if default_match or development_match:
            reason_parts.append(f"standard for {development_type.replace('_', ' ')} projects")
        required_documents = _permit_required_documents(permit, document_requirements)
        evidence = {
            "catalogRule": {
                "permitId": permit.get("id"),
                "permitName": permit.get("permit_name", permit["id"]),
                "supportedDevelopmentTypes": list(supported),
                "defaultForDevelopmentTypes": list(default_for),
                "appliesWhenAny": applies_when,
            },
            "projectFacts": {
                "jurisdiction": project.jurisdiction,
                "projectType": development_type,
                "projectTypeMatchedAs": sorted(development_type_candidates),
                "selectedScope": [key for key, value in scope.items() if value],
                "activeScopeAliases": sorted(active_triggers),
            },
            "matchResult": {
                "triggeredBy": triggered_by,
                "defaultMatch": default_match,
                "developmentTypeMatch": development_match,
                "classification": classification,
            },
        }

        recommendations.append(
            {
                "permit_type": permit["id"],
                "permit_name": permit.get("permit_name", permit["id"]),
                "issuing_authority": permit.get("agency", permit.get("authority", "")),
                "jurisdiction": project.jurisdiction,
                "requirement_status": classification,
                "lifecycle_status": "gathering_documents" if classification == "required" else "not_started",
                "origin": "system",
                "reason": f"{permit.get('permit_name', permit['id'])} applies because " + "; ".join(reason_parts) + ".",
                "recommendation_evidence": evidence,
                "source": permit.get("source_url") or permit.get("source") or permit.get("citation"),
                "portal_url": permit.get("portal_url"),
                "coverage_status": permit.get("coverage_status"),
                "dependencies": permit.get("dependencies", []),
                "required_documents": required_documents,
                "estimated_fee_usd": permit.get("estimated_fee_usd"),
                "next_action": "Confirm whether this permit belongs in the working permit bundle.",
            }
        )
    if project.jurisdiction == "kansas_city_ks":
        recommendations.extend(_exact_kck_application_recommendations(project, scope))

    return recommendations


def _exact_kck_application_recommendations(
    project: Project, scope: dict[str, bool]
) -> list[dict[str, Any]]:
    exact: list[dict[str, Any]] = []
    sources = load_json("source_registry.json", "kansas_city_ks")
    source_map = {item["id"]: item for item in sources.get("sources", [])}
    for application in match_kck_applications(scope, project.project_type):
        source = source_map.get(application["source_id"], {})
        status = application["requirement_status"]
        exact.append(
            {
                "permit_type": f"kck_{application['id']}",
                "permit_name": application["name"],
                "issuing_authority": application["authority"],
                "jurisdiction": project.jurisdiction,
                "requirement_status": status,
                "lifecycle_status": "gathering_documents" if status == "required" else "not_started",
                "origin": "system",
                "reason": application["reason"],
                "recommendation_evidence": {
                    "catalogRule": {
                        "applicationId": application["id"],
                        "category": application["category"],
                        "ruleIds": application["rule_ids"],
                        "sourceIds": application["source_ids"],
                    },
                    "projectFacts": {
                        "jurisdiction": project.jurisdiction,
                        "projectType": project.project_type,
                        "selectedScope": [key for key, value in scope.items() if value],
                    },
                    "matchResult": {
                        "classification": status,
                        "policy": "complete-category deterministic match",
                        "usesVectorOrLlm": False,
                    },
                },
                "source": source.get("title", "Official KCK source registry"),
                "portal_url": source.get("url"),
                "coverage_status": "official_sources_normalized_2026_07_18",
                "dependencies": [],
                "required_documents": list(application.get("documents", [])),
                "estimated_fee_usd": None,
                "next_action": (
                    "Prepare this exact KCK application."
                    if status == "required"
                    else "Confirm the listed condition with the issuing authority; keep this workflow visible until excluded."
                ),
            }
        )
    return exact


def _exact_kcmo_application_recommendations(
    project: Project, scope: dict[str, bool]
) -> list[dict[str, Any]]:
    exact: list[dict[str, Any]] = []
    for application in match_kcmo_applications(scope, project.project_type):
        family = rule_family_for_category(application["category"]) or {}
        application_kind = application["application_kind"]
        application_id = application["id"]
        status = application["requirement_status"]
        required_documents = list(family.get("required_documents", []))
        evidence = {
            "catalogRule": {
                "compassApplicationId": application_id,
                "applicationKind": application_kind,
                "category": application["category"],
                "ruleFamilyId": application.get("rule_family_id"),
                "sourceIds": application.get("sources", []),
            },
            "projectFacts": {
                "jurisdiction": project.jurisdiction,
                "projectType": project.project_type,
                "selectedScope": [key for key, value in scope.items() if value],
            },
            "matchResult": {
                "classification": status,
                "policy": "complete-category deterministic match",
            },
        }
        exact.append(
            {
                "permit_type": f"compass_{application_kind}_{application_id}",
                "permit_name": application["name"],
                "issuing_authority": "Kansas City, Missouri",
                "jurisdiction": project.jurisdiction,
                "requirement_status": status,
                "lifecycle_status": "gathering_documents" if status == "required" else "not_started",
                "origin": "system",
                "reason": application["reason"],
                "recommendation_evidence": evidence,
                "source": "CompassKC Application Assistant",
                "portal_url": application["portal_url"],
                "coverage_status": "live_catalog_snapshot_2026_07_18",
                "dependencies": [],
                "required_documents": required_documents,
                "estimated_fee_usd": None,
                "next_action": (
                    "Prepare this exact CompassKC application."
                    if status == "required"
                    else "Answer the subtype questions to confirm or exclude this exact application."
                ),
            }
        )
    return exact


def _development_type_candidates(development_type: str) -> set[str]:
    aliases = {
        "new_commercial_construction": {"new_commercial_construction", "commercial", "new_construction"},
    }
    return aliases.get(development_type, {development_type})


def _scope_aliases_for(scope: dict[str, bool]) -> set[str]:
    aliases = {
        "alteration": {"interior_alteration"},
        "electrical_work": {"low_voltage_work"},
        "mechanical_hvac_work": {"hvac_work", "kitchen_hood_work"},
        "plumbing_work": {"fixture_relocation"},
        "fire_alarm_sprinkler_work": {"fire_alarm_work", "sprinkler_work"},
        "driveway_sidewalk_row": {"right_of_way_impacts", "construction_staging"},
        "change_use_occupancy": {"change_of_use"},
    }
    active: set[str] = set()
    for key, enabled in scope.items():
        if not enabled:
            continue
        active.add(key)
        active.update(aliases.get(key, set()))
    return active


def _permit_required_documents(permit: dict[str, Any], document_requirements: dict[str, Any]) -> list[str]:
    direct = permit.get("required_documents")
    if isinstance(direct, list) and direct:
        return [str(item) for item in direct]

    configured = document_requirements.get(permit.get("id"), [])
    documents: list[str] = []
    for item in configured:
        if isinstance(item, dict):
            label = item.get("label") or item.get("name") or item.get("key")
            if label:
                documents.append(str(label))
        elif item:
            documents.append(str(item))
    return documents


def _humanize_scope_key(key: str) -> str:
    labels = {
        "mechanical_hvac_work": "mechanical/HVAC work",
        "fire_alarm_sprinkler_work": "fire alarm or sprinkler work",
        "driveway_sidewalk_row": "driveway, sidewalk, or right-of-way impact",
        "solar_battery_generator_ev": "solar, battery, generator, or EV charger work",
        "water_sewer_connections": "water or sewer connection work",
    }
    return labels.get(key, key.replace("_", " "))


def _sync_project_permit_recommendations(project: Project) -> None:
    existing = {p.permit_type: p for p in (project.permits or [])}
    recommendations = {r["permit_type"]: r for r in _candidate_permit_recommendations(project)}
    now = datetime.now(timezone.utc)

    for permit_type, rec in recommendations.items():
        permit = existing.get(permit_type)
        if not permit:
            project.permits.append(
                ProjectPermit(
                    permit_id=str(uuid4()),
                    project_id=project.project_id,
                    updated_at=now,
                    **rec,
                )
            )
            continue

        if permit.origin == "manual" or permit.requirement_status == "removed_by_user":
            continue
        for key, value in rec.items():
            setattr(permit, key, value)
        permit.updated_at = now

    for permit_type, permit in existing.items():
        if permit_type in recommendations:
            continue
        if (
            project.jurisdiction == "kansas_city_mo"
            and permit.origin == "system"
            and permit.requirement_status not in USER_MANAGED_REQUIREMENT_STATUSES
        ):
            project.permits.remove(permit)
            continue
        if permit.origin == "system" and permit.requirement_status not in USER_MANAGED_REQUIREMENT_STATUSES:
            permit.requirement_status = "not_required"
            permit.lifecycle_status = "not_started"
            permit.current_blocker = None
            permit.next_action = "No longer recommended from the current project scope."
            permit.updated_at = now


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
    has_documents = bool(files)
    payload: dict[str, Any] = {}
    for key, config in ANALYSIS_MODULES.items():
        required_any_of = list(config.get("required_any_of", []))
        recommended_missing = [t for t in config["recommended_file_types"] if t not in present_types]
        can_run = has_documents
        payload[key] = {
            "label": config["label"],
            "requiredAnyOf": required_any_of,
            "recommendedFileTypes": config["recommended_file_types"],
            "requiredMissing": [] if can_run else required_any_of,
            "recommendedMissing": recommended_missing,
            "canRun": can_run,
            "hasMappedFiles": False,
            "summary": config.get("summary", ""),
        }
    return payload


_REQUIREMENT_TYPE_HINTS = (
    (("fire", "sprinkler", "alarm", "life safety"), ("fire_protection_plan", "fire_plan")),
    (("mechanical", "hvac"), ("mechanical_plan",)),
    (("plumbing",), ("plumbing_plan",)),
    (("electrical", "lighting", "power"), ("electrical_plan",)),
    (("structural", "foundation", "framing"), ("structural_plan",)),
    (("survey", "plat"), ("survey",)),
    (("civil", "utility", "grading", "stormwater"), ("civil_plan", "site_plan")),
    (("site",), ("site_plan", "civil_plan", "survey")),
    (("elevation",), ("elevation", "architectural_plan")),
    (("architectural", "floor", "drawing", "plan set", "building plan", "construction plan", "parent plan"), ("architectural_plan", "floor_plan")),
    (("code analysis", "code summary"), ("code_analysis",)),
    (("energy", "comcheck"), ("energy_document",)),
    (("application", "form"), ("application_form",)),
    (("authorization", "affidavit", "supporting"), ("supporting_document",)),
)
_REQUIREMENT_STOP_WORDS = {
    "and", "building", "construction", "document", "documents", "drawing", "drawings",
    "existing", "final", "permit", "plan", "plans", "project", "required", "signed", "the",
}


def _file_matches_requirement(project_file: ProjectFile, requirement: str) -> bool:
    normalized = requirement.casefold()
    expected_types: tuple[str, ...] = ()
    for hints, file_types in _REQUIREMENT_TYPE_HINTS:
        if any(hint in normalized for hint in hints):
            expected_types = file_types
            break
    if project_file.file_type in expected_types:
        return True
    searchable = " ".join(
        value for value in (project_file.name, project_file.document_label, project_file.ai_summary) if value
    ).casefold()
    terms = [
        term for term in re.split(r"[^a-z0-9]+", normalized)
        if len(term) > 3 and term not in _REQUIREMENT_STOP_WORDS
    ]
    return any(term in searchable for term in terms)


def _permit_has_review_document(permit: ProjectPermit, files: list[ProjectFile]) -> bool:
    status = _permit_document_status(permit, files)
    if not status["required"]:
        return bool(files)
    return bool(status["found"])


def _permit_document_status(permit: ProjectPermit, files: list[ProjectFile]) -> dict[str, Any]:
    requirements = list(permit.required_documents or [])
    found = [
        requirement for requirement in requirements
        if any(_file_matches_requirement(project_file, requirement) for project_file in files)
    ]
    return {
        "permit_type": permit.permit_type,
        "permit_name": permit.permit_name,
        "required": requirements,
        "found": found,
        "missing": [requirement for requirement in requirements if requirement not in found],
    }


async def analyze_project(
    project_id: str,
    modules: list[str] | None = None,
    permit_types: list[str] | None = None,
) -> dict[str, Any]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.files), selectinload(Project.permits))
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        project_type = ProjectType(project.project_type)
        jurisdiction = project.jurisdiction
        project_name = project.name
        project_address = project.address
        project_area = project.area
        project_zoning_profile = dict(project.zoning_profile or {})
        custom_rules = _usable_custom_rules(project.custom_rules)
        files = list(project.files or [])
        active_permits = [
            permit for permit in (project.permits or [])
            if permit.requirement_status != "not_required"
        ]
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()

    brief = _build_brief_from_project(project)

    if project_area:
        brief.notes = f"{brief.notes or ''}\nArea: {project_area}".strip()

    builtin_rules = await get_builtin_rules_for_project(
        jurisdiction,
        area=project_area,
        project_type=project_type.value,
        zoning_profile=project_zoning_profile,
    )
    custom_rule_names = {str(rule.get("rule", "")).casefold() for rule in custom_rules}
    system_rules = [
        {
            "id": f"system-{index}",
            "category": rule.get("category", "zoning"),
            "rule": rule["rule"],
            "condition": rule["condition"],
            "severity": rule.get("severity", "warning"),
            "enabled": True,
            "source": rule.get("source"),
            "systemManaged": True,
        }
        for index, rule in enumerate(builtin_rules)
        if rule.get("condition") and str(rule.get("rule", "")).casefold() not in custom_rule_names
    ]
    custom_rules = system_rules + custom_rules

    selected_modules = [m for m in (modules or list(ANALYSIS_MODULES.keys())) if m in ANALYSIS_MODULES]
    active_permit_types = {permit.permit_type for permit in active_permits}
    selected_permit_types = list(dict.fromkeys(
        permit_type for permit_type in (permit_types or []) if permit_type in active_permit_types
    ))
    if permit_types and not selected_permit_types:
        raise HTTPException(status_code=400, detail="No eligible permits were selected for review.")
    selected_permits = [
        permit for permit in active_permits
        if not selected_permit_types or permit.permit_type in selected_permit_types
    ]
    if selected_permit_types and not any(
        _permit_has_review_document(permit, files) for permit in selected_permits
    ):
        raise HTTPException(status_code=400, detail="Documents not found")
    requirements = _module_requirements_payload(files)
    document_context = [
        {
            "name": item.name,
            "document_type": item.file_type,
            "label": item.document_label,
            "summary": item.ai_summary or "No AI summary is available for this legacy document.",
            "permit_types": item.permit_types or [],
        }
        for item in files
    ]
    document_context.append(
        {
            "name": "Permit document availability",
            "document_type": "permit_checklist",
            "label": "Found and missing documents for this review",
            "summary": json.dumps([
                _permit_document_status(permit, files) for permit in selected_permits
            ]),
            "permit_types": [permit.permit_type for permit in selected_permits],
        }
    )
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Documents not found",
        )
    if not selected_modules:
        raise HTTPException(status_code=400, detail="No runnable analysis modules selected.")
    return await start_case_async(
        brief,
        project_id=project_id,
        custom_rules=custom_rules,
        selected_modules=selected_modules,
        module_requirements=requirements,
        document_context=document_context,
        target_permit_types=selected_permit_types,
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

    from shared.analysis.runner import _make_llm

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
    zoning_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if jurisdiction == "kansas_city_mo":
        return _build_kcmo_rule_library(
            area=area,
            project_type=project_type,
            zoning_profile=zoning_profile,
        ) + _build_kcmo_permit_review_rules(project_type)
    if jurisdiction == "kansas_city_ks":
        return _build_kck_permit_review_rules()
    if jurisdiction != "manhattan_ks":
        return await get_builtin_rules(jurisdiction)

    with jurisdiction_context(jurisdiction):
        return _build_manhattan_rule_library(
            area=area,
            project_type=project_type,
            zoning_profile=zoning_profile,
        )


def _build_kcmo_rule_library(
    *,
    area: str | None = None,
    project_type: str | None = None,
    zoning_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return build_kcmo_rules(area, zoning_profile, project_type)


def _build_kcmo_permit_review_rules(project_type: str | None = None) -> list[dict[str, Any]]:
    payload = load_json("permit_rules.json", "kansas_city_mo")
    output: list[dict[str, Any]] = []
    for family in payload.get("category_rules", []):
        family_id = family["id"]
        category = KCMO_PERMIT_RULE_CATEGORIES.get(family_id, "permits")
        label = family_id.replace("_", " ").title()
        source = ", ".join(family.get("sources", [])) or "KCMO permit rules"
        generic_types = [family_id, *KCMO_PERMIT_TYPE_ALIASES.get(family_id, [])]
        rule_targets = KCMO_RULE_EXACT_TARGETS.get(family_id, [])
        for index, condition in enumerate(family.get("rules", []), start=1):
            if project_type in {
                "commercial", "commercial_tenant_improvement",
                "new_commercial_construction", "industrial",
            }:
                condition = KCMO_COMMERCIAL_RULE_OVERRIDES.get((family_id, index), condition)
            exact_targets = rule_targets[index - 1] if index <= len(rule_targets) else []
            permit_types = list(exact_targets)
            if not exact_targets or (
                index in KCMO_GENERIC_RULE_INDICES.get(family_id, set())
                and _kcmo_targets_support_project(exact_targets, project_type)
            ):
                permit_types.extend(generic_types)
            output.append(
                {
                    "id": f"kcmo-permit-{family_id}-{index}",
                    "category": category,
                    "group": category,
                    "rule": f"{label} requirement {index}",
                    "condition": condition,
                    "severity": "major",
                    "source": source,
                    "permitTypes": permit_types,
                    "ruleFamilyIds": [] if exact_targets else [family_id],
                }
            )
        exemption_targets = KCMO_EXEMPTION_EXACT_TARGETS.get(family_id, [])
        for index, condition in enumerate(family.get("exemptions", []), start=1):
            exact_targets = exemption_targets[index - 1] if index <= len(exemption_targets) else []
            permit_types = list(exact_targets)
            if not exact_targets or (
                index in KCMO_GENERIC_EXEMPTION_INDICES.get(family_id, set())
                and _kcmo_targets_support_project(exact_targets, project_type)
            ):
                permit_types.extend(generic_types)
            output.append(
                {
                    "id": f"kcmo-permit-{family_id}-exemption-{index}",
                    "category": category,
                    "group": category,
                    "rule": f"{label} exemption {index}",
                    "condition": condition,
                    "severity": "info",
                    "source": source,
                    "permitTypes": permit_types,
                    "ruleFamilyIds": [] if exact_targets else [family_id],
                }
            )
    return output


def _kcmo_targets_support_project(targets: list[str], project_type: str | None) -> bool:
    if not project_type or project_type == "mixed_use":
        return True
    residential_project = project_type in {"single_family", "multifamily_residential"}
    residential_targets = [target for target in targets if target in KCMO_RESIDENTIAL_EXACT_TYPES]
    if residential_project:
        return bool(residential_targets)
    return len(residential_targets) < len(targets)


def _build_kck_permit_review_rules() -> list[dict[str, Any]]:
    rules_payload = load_json("permit_rules.json", "kansas_city_ks")
    catalog = load_json("application_catalog.json", "kansas_city_ks")
    applications = {item["id"]: item for item in catalog.get("applications", [])}
    category_ids: dict[str, list[str]] = {}
    for application in applications.values():
        category_ids.setdefault(application["category"], []).append(application["id"])

    category_to_group = {
        "Building and Trade": "building",
        "Planning and Land Use": "zoning",
        "Public Works and Utilities": "site",
        "Fire Prevention": "fire",
    }
    output: list[dict[str, Any]] = []
    for rule in rules_payload.get("rules", []):
        application_ids: set[str] = set()
        matched_categories: set[str] = set()
        for target in rule.get("applies_to", []):
            if target in category_ids:
                matched_categories.add(target)
                application_ids.update(category_ids[target])
            elif target in applications:
                application_ids.add(target)
                matched_categories.add(applications[target]["category"])

        permit_types = set(application_ids)
        for application_id in application_ids:
            permit_types.update(KCK_APPLICATION_GENERIC_ALIASES.get(application_id, []))
        if "Planning and Land Use" in matched_categories:
            permit_types.add("planning_entitlement")

        group = "building"
        if len(matched_categories) == 1:
            group = category_to_group.get(next(iter(matched_categories)), "building")
        elif "Fire Prevention" in matched_categories:
            group = "fire"
        elif "Public Works and Utilities" in matched_categories:
            group = "site"

        output.append(
            {
                "id": f"kck-permit-{rule['id']}",
                "category": group,
                "group": group,
                "rule": rule["id"].replace("_", " ").title(),
                "condition": rule["rule"],
                "severity": "major",
                "source": ", ".join(rule.get("source_ids", [])) or "KCK official permit rules",
                "permitTypes": sorted(permit_types),
                "ruleFamilyIds": [],
            }
        )
    return output


def _build_manhattan_rule_library(
    *,
    area: str | None = None,
    project_type: str | None = None,
    zoning_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    area_token = (area or "").strip().upper()
    rules: list[dict[str, Any]] = build_manhattan_rules(area_token, zoning_profile)

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
    for permit in catalog.get("permit_types", []) or catalog.get("permits", []):
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
    area_tokens = {token.strip() for token in area_token.split("/") if token.strip()}
    if not area_tokens or not area_tokens.issubset(MANHATTAN_DISTRICT_TOKENS):
        return True
    haystack = f"{chunk.get('title', '')} {chunk.get('text', '')}"
    if any(re.search(rf"\b{re.escape(token)}\b", haystack) for token in area_tokens):
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
