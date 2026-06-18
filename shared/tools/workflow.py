from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from shared.band_client import orchestrator as band_orchestrator
from shared.schemas.project_brief import ProjectBrief

logger = logging.getLogger(__name__)


def _orchestration_mode() -> str:
    return os.getenv("PERMITOS_ORCHESTRATION", "band").lower()


async def run_workflow_with_activity_async(
    brief: ProjectBrief,
    band_room_id: str | None = None,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict:
    mode = _orchestration_mode()

    if mode == "local":
        from shared.agent_logic.local_runner import run_local_case

        logger.warning("PERMITOS_ORCHESTRATION=local — not using Band")
        return await run_local_case(brief)

    logger.info("Running Band orchestration for case %s (room=%s)", brief.case_id, band_room_id)
    return await band_orchestrator.run_band_case(
        brief, existing_room_id=band_room_id, on_progress=on_progress
    )


def run_workflow_with_activity(brief: ProjectBrief, band_room_id: str | None = None) -> dict:
    import asyncio

    return asyncio.run(run_workflow_with_activity_async(brief, band_room_id=band_room_id))
