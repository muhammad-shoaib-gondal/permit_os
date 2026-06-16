"""Agent pipeline errors."""

from __future__ import annotations


class AgentPipelineError(RuntimeError):
    """Base error for agent workflow failures."""


class AgentQuotaError(AgentPipelineError):
    """LLM provider quota / credits exhausted."""


def is_llm_quota_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "402",
            "429",
            "depleted",
            "quota",
            "rate limit",
            "insufficient",
            "credits",
            "payment required",
        )
    )
