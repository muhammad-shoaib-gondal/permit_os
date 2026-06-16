"""Band-only workflow — live agents on Band.ai; no local rule engine."""

from __future__ import annotations

from shared.band_client import orchestrator as band_orchestrator
from shared.schemas.project_brief import ProjectBrief


async def run_workflow_with_activity_async(
    brief: ProjectBrief, band_room_id: str | None = None
) -> dict:
    """Run permit case through live Band agents (REST dispatch + poll)."""
    result = await band_orchestrator.run_band_case(brief)
    if band_room_id:
        result["band_room_id"] = band_room_id
    return result


def run_workflow_with_activity(brief: ProjectBrief, band_room_id: str | None = None) -> dict:
    import asyncio

    return asyncio.run(run_workflow_with_activity_async(brief, band_room_id=band_room_id))
