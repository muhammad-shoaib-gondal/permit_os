from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from shared.schemas.project_brief import ProjectBrief

logger = logging.getLogger(__name__)


async def run_workflow_with_activity_async(
    brief: ProjectBrief,
    on_progress: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    custom_rules: list[dict[str, Any]] | None = None,
    selected_modules: list[str] | None = None,
    module_requirements: dict[str, Any] | None = None,
) -> dict:
    """Run the permit analysis directly through ZenMux."""
    from shared.analysis.runner import run_analysis
    from shared.llm.zenmux import resolve_zenmux_config
    from shared.tools.knowledge import jurisdiction_context

    resolve_zenmux_config()
    jurisdiction = getattr(brief, "jurisdiction", None) or "austin_tx"
    logger.info("Running direct analysis for case %s", brief.case_id)
    with jurisdiction_context(jurisdiction):
        return await run_analysis(
            brief,
            on_progress=on_progress,
            custom_rules=custom_rules,
            selected_modules=selected_modules,
            module_requirements=module_requirements,
        )


def run_workflow_with_activity(brief: ProjectBrief) -> dict:
    import asyncio

    return asyncio.run(run_workflow_with_activity_async(brief))
