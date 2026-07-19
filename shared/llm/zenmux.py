"""Single-provider ZenMux integration for every EstatePermit AI operation."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any

import httpx

ZENMUX_DEFAULT_BASE_URL = "https://zenmux.ai/api/v1"
ZENMUX_DEFAULT_MODEL = "moonshotai/kimi-k3-free"


@dataclass(frozen=True)
class ZenMuxConfig:
    api_key: str
    base_url: str
    model: str
    max_tokens: int
    max_retries: int
    timeout_seconds: float


def resolve_zenmux_config() -> ZenMuxConfig:
    """Load the only supported LLM configuration."""
    api_key = os.getenv("ZENMUX_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "ZenMux is required for analysis. Set ZENMUX_API_KEY in the repository .env file."
        )

    return ZenMuxConfig(
        api_key=api_key,
        base_url=os.getenv("ZENMUX_BASE_URL", ZENMUX_DEFAULT_BASE_URL).rstrip("/"),
        model=os.getenv("ZENMUX_MODEL", ZENMUX_DEFAULT_MODEL),
        max_tokens=int(os.getenv("ZENMUX_MAX_TOKENS", "8192")),
        max_retries=int(os.getenv("ZENMUX_MAX_RETRIES", "4")),
        timeout_seconds=float(os.getenv("ZENMUX_TIMEOUT_SEC", "180")),
    )


def orchestration_hint() -> str:
    """Short user-facing message when analysis does not complete."""
    return "Something went wrong - we couldn't complete the analysis."


def create_chat_model():
    """Create the ZenMux-backed LangChain model used by all analysis paths."""
    from langchain_openai import ChatOpenAI

    config = resolve_zenmux_config()
    kwargs: dict[str, Any] = {
        "model": config.model,
        "base_url": config.base_url,
        "api_key": config.api_key,
        "max_tokens": config.max_tokens,
        "max_retries": config.max_retries,
        "timeout": config.timeout_seconds,
    }

    return ChatOpenAI(**kwargs)


async def chat_completion(
    purpose: str,
    messages: list[dict[str, Any]],
    *,
    max_tokens: int | None = None,
) -> str:
    """Run an OpenAI-compatible chat completion through ZenMux."""
    del purpose
    config = resolve_zenmux_config()
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "max_tokens": max_tokens or config.max_tokens,
    }

    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        response = await client.post(
            f"{config.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


async def extract_pdf_text(pdf_bytes: bytes, prompt: str | None = None) -> str:
    """Send a PDF extraction request through the configured ZenMux model."""
    encoded = base64.standard_b64encode(pdf_bytes).decode("ascii")
    instruction = prompt or (
        "Extract the permitting facts from this project PDF, including dimensions, "
        "setbacks, occupancy, construction type, systems, and plan notes."
    )
    return await chat_completion(
        "document_extraction",
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {
                        "type": "file",
                        "file": {
                            "filename": "project.pdf",
                            "file_data": f"data:application/pdf;base64,{encoded}",
                        },
                    },
                ],
            }
        ],
        max_tokens=4096,
    )
