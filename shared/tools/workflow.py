"""Workflow runner — uses direct LLM API calls, no external agent framework."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from shared.schemas.project_brief import ProjectBrief

logger = logging.getLogger(__name__)


async def run_workflow_with_activity_async(
    brief: ProjectBrief,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> dict:
    from shared.agent_logic.local_runner import run_local_case

    logger.info("Running LLM pipeline for case %s", brief.case_id)
    return await run_local_case(brief, on_progress=on_progress)


def run_workflow_with_activity(brief: ProjectBrief) -> dict:
    import asyncio

    return asyncio.run(run_workflow_with_activity_async(brief))
