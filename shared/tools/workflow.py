from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from shared.band_client import orchestrator as band_orchestrator
from shared.schemas.project_brief import ProjectBrief

logger = logging.getLogger(__name__)


def video_mode_enabled() -> bool:
    return os.getenv("PERMITOS_VIDEO_MODE", "").lower() in ("1", "true", "yes")


def _orchestration_mode() -> str:
    """Resolve orchestration mode without silently doubling LLM calls in band mode."""
    if video_mode_enabled():
        return "local"

    explicit = os.getenv("PERMITOS_ORCHESTRATION")
    if explicit and explicit.lower() not in ("auto", ""):
        return explicit.lower()

    from shared.band_client.config import agent_config_available

    if agent_config_available():
        return "band"
    return "local"


def _band_explicitly_requested() -> bool:
    return os.getenv("PERMITOS_ORCHESTRATION", "").lower() == "band"


async def run_workflow_with_activity_async(
    brief: ProjectBrief,
    band_room_id: str | None = None,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict:
    mode = _orchestration_mode()

    if mode == "local":
        from shared.agent_logic.local_runner import run_local_case

        if video_mode_enabled():
            logger.info("PERMITOS_VIDEO_MODE=1 — fast demo path (no Band, no LLM)")
        else:
            logger.info("PERMITOS_ORCHESTRATION=local for case %s", brief.case_id)
        return await run_local_case(brief, on_progress=on_progress)

    from shared.band_client.config import agent_config_available

    if not agent_config_available():
        msg = (
            "Band credentials not configured. Add agent_config.yaml (or Render secret file) "
            "before running PERMITOS_ORCHESTRATION=band."
        )
        if _band_explicitly_requested():
            raise FileNotFoundError(msg)
        logger.warning("%s — falling back to local orchestration", msg)
        from shared.agent_logic.local_runner import run_local_case

        return await run_local_case(brief, on_progress=on_progress)

    logger.info("Running Band orchestration for case %s (room=%s)", brief.case_id, band_room_id)
    # Never fall back to local when band mode is active: local_runner would call the
    # same LLM while Band agent processes are also running (Render all-in-one → 429s).
    return await band_orchestrator.run_band_case(
        brief, existing_room_id=band_room_id, on_progress=on_progress
    )


def run_workflow_with_activity(brief: ProjectBrief, band_room_id: str | None = None) -> dict:
    import asyncio

    return asyncio.run(run_workflow_with_activity_async(brief, band_room_id=band_room_id))
