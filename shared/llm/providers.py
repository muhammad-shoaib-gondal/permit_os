from __future__ import annotations

import base64
import os
from enum import Enum
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Provider(str, Enum):
    AIML_API = "aiml_api"
    FEATHERLESS = "featherless"
    OPENAI = "openai"


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aiml_api_key: str | None = None
    aiml_api_base: str = "https://api.aimlapi.com/v1"
    featherless_api_key: str | None = None
    featherless_api_base: str = "https://api.featherless.ai/v1"
    openai_api_key: str | None = None


AGENT_MODELS: dict[str, tuple[Provider, str]] = {
    "conductor": (Provider.AIML_API, "gpt-4o-mini"),
    "jurisdiction": (Provider.FEATHERLESS, "meta-llama/Llama-3.3-70B-Instruct"),
    "building": (Provider.AIML_API, "anthropic/claude-3-5-sonnet-latest"),
    "site": (Provider.FEATHERLESS, "Qwen/Qwen2.5-72B-Instruct"),
    "packager": (Provider.AIML_API, "anthropic/claude-3-5-sonnet-latest"),
}


def _settings() -> LLMSettings:
    return LLMSettings()


def get_model_for_agent(agent: str) -> tuple[Provider, str]:
    return AGENT_MODELS.get(agent, (Provider.OPENAI, "gpt-4o-mini"))


def _resolve_credentials(provider: Provider) -> tuple[str, str]:
    s = _settings()
    if provider == Provider.AIML_API:
        key = s.aiml_api_key or os.getenv("AIML_API_KEY") or s.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("Set AIML_API_KEY (or OPENAI_API_KEY as fallback) for AI/ML API routing")
        return s.aiml_api_base, key
    if provider == Provider.FEATHERLESS:
        key = s.featherless_api_key or os.getenv("FEATHERLESS_API_KEY")
        if not key:
            raise ValueError("Set FEATHERLESS_API_KEY for Featherless inference")
        return s.featherless_api_base, key
    key = s.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("Set OPENAI_API_KEY")
    return "https://api.openai.com/v1", key


async def chat_completion(
    agent: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """Route chat completion to the configured provider for an agent role."""
    from shared.llm.backends import get_backend, resolve_llm_config

    backend = get_backend()
    if backend.value in ("huggingface", "ollama", "featherless", "aiml_api", "openai"):
        base_url, api_key, model = resolve_llm_config()
    else:
        provider, model = get_model_for_agent(agent)
        base_url, api_key = _resolve_credentials(provider)

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]


async def extract_pdf_text(pdf_bytes: bytes, prompt: str | None = None) -> str:
    """Multimodal PDF extraction via AI/ML API (vision-capable model)."""
    s = _settings()
    base_url, api_key = _resolve_credentials(Provider.AIML_API)
    b64 = base64.standard_b64encode(pdf_bytes).decode()
    user_prompt = prompt or (
        "Extract all text from this site plan PDF. Focus on setbacks, block labels, "
        "dimensions, and any notes about building footprints."
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:application/pdf;base64,{b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 2048,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code >= 400:
            # Fallback: return placeholder when vision PDF not supported
            return "PDF uploaded — enable AIML_API_KEY for multimodal extraction."
        data = resp.json()
    return data["choices"][0]["message"]["content"]
