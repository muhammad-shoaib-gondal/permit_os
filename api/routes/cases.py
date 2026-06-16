from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.case_service import approve_case, create_case, get_case
from shared.agent_logic.errors import AgentPipelineError, AgentQuotaError
from shared.band_client.orchestrator import BandOrchestrationError
from shared.schemas.project_brief import ProjectBrief, ProjectType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])


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


@router.get("/demo/riverside")
async def demo_riverside():
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
    return {
        "case_id": case.case_id,
        "project_name": case.project_name,
        "status": case.status,
        "band_room_id": case.band_room_id,
        "audit_hash": case.audit_hash,
        "approved_by": case.approved_by,
        "approved_at": case.approved_at.isoformat() if case.approved_at else None,
        "results": case.results,
    }


@router.post("/{case_id}/approve")
async def post_approve(case_id: UUID, body: ApproveRequest):
    result = await approve_case(str(case_id), body.approved_by)
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")
    return result
