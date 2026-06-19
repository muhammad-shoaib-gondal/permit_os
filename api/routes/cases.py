from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from api.services.case_service import approve_case, create_case, get_case, start_case_async
from api.services.intake import parse_intake_upload
from shared.agent_logic.errors import AgentPipelineError, AgentQuotaError
from shared.band_client.orchestrator import BandOrchestrationError
from shared.schemas.project_brief import ProjectBrief, ProjectType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])


def _is_case_stale(case) -> bool:
    """True when analysis has had no progress for too long (Band room likely silent)."""
    if case.status != "ANALYZING":
        return False
    results = case.results or {}
    last_at = results.get("last_progress_at")
    if not last_at:
        return False
    try:
        ts = datetime.fromisoformat(str(last_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    age_sec = (datetime.now(timezone.utc) - ts).total_seconds()
    has_reports = any(results.get(f"{a}_report") for a in ("jurisdiction", "building", "site"))
    threshold = 180 if has_reports else 120
    return age_sec > threshold


def _handle_pipeline_error(exc: Exception) -> None:
    if isinstance(exc, BandOrchestrationError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, AgentQuotaError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, AgentPipelineError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    logger.exception("Case pipeline failed")
    raise HTTPException(status_code=500, detail=str(exc)) from exc


class CreateCaseRequest(BaseModel):
    project_name: str
    address: str
    project_type: ProjectType = ProjectType.MULTIFAMILY_RESIDENTIAL
    units: int
    stories: int
    gross_sqft: int
    lot_sqft: int
    parking_spaces: int
    notes: Optional[str] = None
    use_demo: bool = False


class ApproveRequest(BaseModel):
    approved_by: str = "human-reviewer"


@router.post("")
async def post_case(body: CreateCaseRequest):
    if body.use_demo:
        brief = ProjectBrief.riverside_residences_demo()
    else:
        brief = ProjectBrief(
            project_name=body.project_name,
            address=body.address,
            project_type=body.project_type,
            units=body.units,
            stories=body.stories,
            gross_sqft=body.gross_sqft,
            lot_sqft=body.lot_sqft,
            parking_spaces=body.parking_spaces,
            notes=body.notes,
        )
    try:
        results = await create_case(brief, demo=body.use_demo)
    except (BandOrchestrationError, AgentQuotaError, AgentPipelineError, RuntimeError) as exc:
        _handle_pipeline_error(exc)
    return {"case_id": str(brief.case_id), "band_room_id": results["case_summary"].get("band_room_id"), **results}


@router.post("/analyze")
async def analyze_intake(
    file: UploadFile = File(...),
    project_type: ProjectType = Form(ProjectType.MULTIFAMILY_RESIDENTIAL),
    jurisdiction: str = Form("austin_tx"),
):
    """Upload project brief (.json) or package (.zip) and start Band analysis."""
    if jurisdiction != "austin_tx":
        raise HTTPException(status_code=400, detail="Only Austin, TX is supported in this MVP.")
    brief, _ = await parse_intake_upload(file, project_type)
    return await start_case_async(brief)


@router.post("/demo/riverside")
async def demo_riverside_start():
    """Start Riverside demo — returns immediately; poll GET /cases/{case_id} for results."""
    brief = ProjectBrief.riverside_residences_demo()
    return await start_case_async(brief)


@router.get("/demo/riverside")
async def demo_riverside():
    """Legacy sync demo (may timeout). Prefer POST /demo/riverside."""
    brief = ProjectBrief.riverside_residences_demo()
    try:
        results = await create_case(brief, demo=True)
    except (BandOrchestrationError, AgentQuotaError, AgentPipelineError, RuntimeError) as exc:
        _handle_pipeline_error(exc)
    return {"case_id": str(brief.case_id), **results}


@router.get("/{case_id}")
async def get_case_by_id(case_id: UUID):
    case = await get_case(str(case_id))
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    results = case.results or {}
    return {
        "case_id": case.case_id,
        "project_name": case.project_name,
        "status": case.status,
        "band_room_id": case.band_room_id,
        "audit_hash": case.audit_hash,
        "approved_by": case.approved_by,
        "approved_at": case.approved_at.isoformat() if case.approved_at else None,
        "results": results,
        "is_stale": _is_case_stale(case),
        "stalled": bool(results.get("stalled")),
        "stall_reason": results.get("stall_reason"),
        "error": results.get("error") if case.status == "FAILED" else None,
        "error_detail": results.get("error_detail") if case.status == "FAILED" else None,
    }


@router.post("/{case_id}/approve")
async def post_approve(case_id: UUID, body: ApproveRequest):
    result = await approve_case(str(case_id), body.approved_by)
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")
    return result
