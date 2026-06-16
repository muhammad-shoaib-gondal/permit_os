from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.case_service import get_audit_log, simulate_rfi

router = APIRouter(prefix="/cases", tags=["audit"])


class RfiRequest(BaseModel):
    rfi_text: str = "Provide fire apparatus access diagram for Block B east setback area."


@router.get("/{case_id}/audit")
async def get_case_audit(case_id: UUID):
    entries = await get_audit_log(str(case_id))
    if not entries:
        raise HTTPException(status_code=404, detail="No audit log for case")
    return {"case_id": str(case_id), "entries": entries}


@router.post("/{case_id}/rfi")
async def post_rfi(case_id: UUID, body: RfiRequest):
    result = await simulate_rfi(str(case_id), body.rfi_text)
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")
    return result
