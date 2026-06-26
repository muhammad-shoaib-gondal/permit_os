"""Central application configuration."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentRole(str, Enum):
    CONDUCTOR = "conductor"
    JURISDICTION = "jurisdiction"
    BUILDING = "building"
    SITE = "site"
    PACKAGER = "packager"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./permitos.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    openai_api_key: Optional[str] = None


def load_settings() -> Settings:
    return Settings()
