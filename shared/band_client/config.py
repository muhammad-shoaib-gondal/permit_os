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


def _config_candidates() -> list[Path]:
    """Paths where Band credentials may live (local dev + Render /etc/secrets)."""
    root = Path(__file__).resolve().parents[2]
    names = (
        "agent_config.yaml",
        "agent_config.yml",
        "agents_config.yaml",
        "agents_config.yml",
    )
    candidates: list[Path] = []

    custom = os.getenv("AGENT_CONFIG_PATH")
    if custom:
        candidates.append(Path(custom))

    for name in names:
        candidates.append(root / name)

    # Render Secret Files: /etc/secrets/<filename>
    secrets_root = Path("/etc/secrets")
    if secrets_root.is_dir():
        for name in names:
            candidates.append(secrets_root / name)

    return candidates


def _config_path() -> Path:
    for path in _config_candidates():
        if path.exists():
            return path
    return Path(__file__).resolve().parents[2] / "agent_config.yaml"


def _load_config_from_file() -> dict:
    for path in _config_candidates():
        if path.exists():
            with path.open(encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}


def _load_config_data() -> dict:
    """Load Band credentials from env vars, inline YAML, or config file."""
    inline = os.getenv("AGENT_CONFIG_YAML") or os.getenv("AGENTS_CONFIG_YAML")
    if inline:
        data = yaml.safe_load(inline) or {}
        if data:
            return data

    data = _load_config_from_file()
    if data:
        return data

    data: dict = {}
    for role in AgentRole:
        prefix = role.value.upper()
        agent_id = os.getenv(f"{prefix}_AGENT_ID") or os.getenv(f"BAND_{prefix}_AGENT_ID")
        api_key = (
            os.getenv(f"{prefix}_API_KEY")
            or os.getenv(f"{prefix}_BAND_API_KEY")
            or os.getenv(f"BAND_{prefix}_API_KEY")
        )
        if agent_id and api_key:
            data[role.value] = {"agent_id": agent_id, "api_key": api_key}
    return data


def agent_config_available() -> bool:
    """True when conductor credentials are configured (file, env YAML, or env vars)."""
    data = _load_config_data()
    entry = data.get(AgentRole.CONDUCTOR.value) or {}
    agent_id = entry.get("agent_id", "")
    api_key = entry.get("api_key", "")
    return bool(agent_id and api_key and "your-" not in str(agent_id))


def get_agent_credentials(role: AgentRole) -> tuple[str, str]:
    data = _load_config_data()
    if not data:
        raise FileNotFoundError(
            "Missing Band agent credentials. Add agent_config.yaml, set AGENT_CONFIG_YAML, "
            "or set CONDUCTOR_AGENT_ID + CONDUCTOR_API_KEY (and other agents) in environment."
        )
    entry = data.get(role.value)
    if not entry:
        raise KeyError(f"No credentials for agent role '{role.value}'")
    agent_id = entry.get("agent_id", "")
    api_key = entry.get("api_key", "")
    if not agent_id or not api_key or "your-" in str(agent_id):
        raise ValueError(
            f"Invalid credentials for '{role.value}'. Register agent on Band and update config."
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
