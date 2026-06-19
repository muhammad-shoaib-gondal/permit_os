from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from shared.band_client import orchestrator as band_orchestrator
from shared.schemas.project_brief import ProjectBrief

logger = logging.getLogger(__name__)


def _orchestration_mode() -> str:
    explicit = os.getenv("PERMITOS_ORCHESTRATION")
    if explicit:
        return explicit.lower()
    from shared.band_client.config import _config_path

    if _config_path().exists():
        return "band"
    return "local"


async def run_workflow_with_activity_async(
    brief: ProjectBrief,
    band_room_id: str | None = None,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict:
    mode = _orchestration_mode()

    if mode == "band":
        from shared.band_client.config import _config_path

        if not _config_path().exists():
            logger.warning("agent_config.yaml missing on server — falling back to local orchestration")
            mode = "local"

    if mode == "local":
        from shared.agent_logic.local_runner import run_local_case

        logger.info("PERMITOS_ORCHESTRATION=local for case %s", brief.case_id)
        return await run_local_case(brief)

    logger.info("Running Band orchestration for case %s (room=%s)", brief.case_id, band_room_id)
    try:
        return await band_orchestrator.run_band_case(
            brief, existing_room_id=band_room_id, on_progress=on_progress
        )
    except FileNotFoundError as exc:
        logger.warning("Band credentials unavailable (%s) — falling back to local orchestration", exc)
        from shared.agent_logic.local_runner import run_local_case

        return await run_local_case(brief)


def run_workflow_with_activity(brief: ProjectBrief, band_room_id: str | None = None) -> dict:
    import asyncio

    return asyncio.run(run_workflow_with_activity_async(brief, band_room_id=band_room_id))
