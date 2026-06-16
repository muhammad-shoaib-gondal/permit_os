from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentRole(str, Enum):
    CONDUCTOR = "conductor"
    JURISDICTION = "jurisdiction"
    BUILDING = "building"
    SITE = "site"
    PACKAGER = "packager"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    band_ws_url: str = "wss://app.band.ai/api/v1/socket/websocket"
    band_rest_url: str = "https://app.band.ai"
    # Legacy env names
    thenvoi_ws_url: Optional[str] = None
    thenvoi_rest_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    aiml_api_key: Optional[str] = None
    featherless_api_key: Optional[str] = None
    database_url: str = "sqlite+aiosqlite:///./permitos.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    permitos_demo_mode: bool = False


def load_settings() -> Settings:
    return Settings()


def _config_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    for name in ("agent_config.yaml", "agent_config.yml"):
        path = root / name
        if path.exists():
            return path
    return root / "agent_config.yaml"


def get_agent_credentials(role: AgentRole) -> tuple[str, str]:
    path = _config_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path.name}. Copy agent_config.yaml.example and add Band credentials."
        )
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entry = data.get(role.value)
    if not entry:
        raise KeyError(f"No credentials for agent role '{role.value}' in {path.name}")
    agent_id = entry.get("agent_id", "")
    api_key = entry.get("api_key", "")
    if not agent_id or not api_key or "your-" in str(agent_id):
        raise ValueError(
            f"Invalid credentials for '{role.value}'. Register agent on Band and update {path.name}."
        )
    return agent_id, api_key


def band_urls() -> dict[str, str]:
    settings = load_settings()
    ws = (
        os.getenv("BAND_WS_URL")
        or settings.band_ws_url
        or settings.thenvoi_ws_url
        or os.getenv("THENVOI_WS_URL")
    )
    rest = (
        os.getenv("BAND_REST_URL")
        or settings.band_rest_url
        or settings.thenvoi_rest_url
        or os.getenv("THENVOI_REST_URL")
    )
    return {
        "ws_url": ws or "wss://app.band.ai/api/v1/socket/websocket",
        "rest_url": rest or "https://app.band.ai",
    }
