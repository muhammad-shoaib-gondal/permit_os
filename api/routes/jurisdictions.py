from __future__ import annotations

from fastapi import APIRouter

from shared.tools.knowledge import list_jurisdictions

router = APIRouter(tags=["jurisdictions"])


@router.get("/jurisdictions")
async def get_jurisdictions():
    return list_jurisdictions()
