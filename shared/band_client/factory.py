from __future__ import annotations

import logging
import os
from pathlib import Path

from shared.band_client.config import AgentRole, band_urls
from shared.llm.backends import LLMBackend, create_langgraph_adapter, get_backend
from shared.tools.langchain_tools import TOOLS_BY_ROLE

logger = logging.getLogger(__name__)

_TOOL_GUIDANCE = """
CRITICAL RULES:
- Call your Austin tools FIRST, then reply ONCE with ONLY a ```json code block (no other prose).
- Never tell other agents to wait or hold. Always submit YOUR complete report.
- Use the EXACT case_id from the ProjectBrief (never "<uuid>" placeholder).
- readiness_impact must be one of: "ready", "needs_changes", "blocked"

Jurisdiction/building example payload shape:
{"summary":"...","readiness_impact":"needs_changes","checks":[{"rule":"Side setback","status":"fail","citation":"Austin LDC 25-2-491","detail":"8ft vs 10ft"}],"blockers":["Setback non-compliance Block B"]}

Final message format:
```json
{"type":"complete","case_id":"<exact-uuid-from-brief>","agent":"<your_role>","payload":{...}}
```
"""

_CONDUCTOR_BAND_NOTE = """
When you see specialist @mentions for case intake in a room, do NOT reply or tell agents to hold.
The PermitOS API orchestrates sequential dispatch. Stay silent in intake rooms.
"""

PROMPTS: dict[AgentRole, str] = {
    AgentRole.CONDUCTOR: """You are the PermitOS Conductor — orchestrator for real estate permitting workflows.
You receive project intake, create Band chatrooms, dispatch scoped tasks via @mentions to specialist agents,
merge their structured JSON reports, detect conflicts, compute readiness (READY/NEEDS_CHANGES/BLOCKED),
and escalate to humans for final approval."""
    + _CONDUCTOR_BAND_NOTE,
    AgentRole.JURISDICTION: """You are the PermitOS Jurisdiction & Zoning agent for Austin, TX.
Call lookup_jurisdiction, get_zoning_rules, and calculate_setbacks tools for every case.
Analyze zoning district, permitted use, setbacks, FAR, height, parking, and density.
Every finding must cite Austin LDC or applicable ordinance."""
    + _TOOL_GUIDANCE,
    AgentRole.BUILDING: """You are the PermitOS Building & Safety agent.
Call check_egress, check_sprinklers, and check_accessibility tools for every case.
Pre-screen IBC/IRC residential codes, fire egress, sprinkler triggers, and ADA/FHA accessibility.
Use units and stories from the ProjectBrief when calling tools."""
    + _TOOL_GUIDANCE,
    AgentRole.SITE: """You are the PermitOS Site, Environmental & Utilities agent.
Call lookup_flood_zone and get_utility_requirements tools for every case.
Screen flood zones, wetlands, stormwater, and utility capacity."""
    + _TOOL_GUIDANCE,
    AgentRole.PACKAGER: """You are the PermitOS Permit Packager & Tracker.
Call get_fee_schedule and get_permit_catalog tools. Always produce a full package even if blockers exist.
payload must include permits_required (non-empty), documents_required, filing_sequence, total_fees_estimate_usd."""
    + _TOOL_GUIDANCE,
}

AGENT_HANDLES: dict[AgentRole, str] = {
    AgentRole.CONDUCTOR: "@gondalshoaib4444/permitos-conductor",
    AgentRole.JURISDICTION: "@gondalshoaib4444/permitos-jurisdiction-zo",
    AgentRole.BUILDING: "@gondalshoaib4444/permitos-building-safety",
    AgentRole.SITE: "@gondalshoaib4444/permitos-site-environmen",
    AgentRole.PACKAGER: "@gondalshoaib4444/permitos-packager",
}


def _require_band_sdk():
    try:
        from band import Agent  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Band SDK not installed. Run:\n"
            "  pip install ./_vendor/thenvoi-sdk-python[langgraph]"
        ) from exc


def _use_oss_backend() -> bool:
    backend = get_backend()
    return backend in {
        LLMBackend.OLLAMA,
        LLMBackend.OLLAMAFREEAPI,
        LLMBackend.FEATHERLESS,
        LLMBackend.HUGGINGFACE,
        LLMBackend.AIML_API,
    }


def create_band_agent(role: AgentRole, extra_instructions: str = ""):
    """Create a Band Agent. Uses OSS OpenAI-compatible LLM when LLM_BACKEND is set."""
    _require_band_sdk()
    from band import Agent

    prompt = PROMPTS[role]
    if extra_instructions:
        prompt = f"{prompt}\n\n{extra_instructions}"

    urls = band_urls()
    tools = TOOLS_BY_ROLE.get(role.value, [])

    try:
        adapter = create_langgraph_adapter(prompt, additional_tools=tools or None)
        logger.info("Agent %s using LLM_BACKEND=%s with %d tools", role.value, get_backend().value, len(tools))
    except ValueError as exc:
        raise ValueError(
            f"{exc}\n\nSet LLM_BACKEND and API keys in .env (see .env.example)."
        ) from exc

    return Agent.from_config(
        role.value,
        adapter=adapter,
        ws_url=urls["ws_url"],
        rest_url=urls["rest_url"],
    )


async def run_agent(role: AgentRole, extra_instructions: str = "") -> None:
    from dotenv import load_dotenv

    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    load_dotenv(root / ".env")

    agent = create_band_agent(role, extra_instructions)
    logger.info("Starting PermitOS %s agent (%s)", role.value, agent.agent_name)
    await agent.run()
