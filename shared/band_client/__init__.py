"""Shared Band / Thenvoi client helpers for PermitOS agents."""

from shared.band_client.config import AgentRole, get_agent_credentials, load_settings
from shared.band_client.messaging import build_band_message, parse_band_message

__all__ = [
    "AgentRole",
    "build_band_message",
    "create_band_agent",
    "get_agent_credentials",
    "load_settings",
    "parse_band_message",
    "run_agent",
]


def __getattr__(name: str):
    if name == "create_band_agent":
        from shared.band_client.factory import create_band_agent

        return create_band_agent
    if name == "run_agent":
        from shared.band_client.factory import run_agent

        return run_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
