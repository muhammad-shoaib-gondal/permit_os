"""Central application configuration."""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./EstatePermit.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    zenmux_api_key: Optional[str] = None


def load_settings() -> Settings:
    return Settings()
