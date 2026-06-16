"""OpenAI-compatible LLM backends for Band agents (Ollama, Featherless, Hugging Face)."""

from __future__ import annotations

import os
from enum import Enum

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from band.adapters import LangGraphAdapter


class LLMBackend(str, Enum):
    OLLAMA = "ollama"
    FEATHERLESS = "featherless"
    HUGGINGFACE = "huggingface"
    OPENAI = "openai"
    AIML_API = "aiml_api"


BACKEND_DEFAULTS: dict[LLMBackend, dict[str, str]] = {
    LLMBackend.OLLAMA: {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "llama3.2",
    },
    LLMBackend.FEATHERLESS: {
        "base_url": "https://api.featherless.ai/v1",
        "api_key": "",  # from FEATHERLESS_API_KEY
        "model": "meta-llama/Llama-3.3-70B-Instruct",
    },
    LLMBackend.HUGGINGFACE: {
        "base_url": "https://router.huggingface.co/v1",
        "api_key": "",  # from HF_TOKEN
        "model": "Qwen/Qwen2.5-7B-Instruct",
    },
    LLMBackend.AIML_API: {
        "base_url": "https://api.aimlapi.com/v1",
        "api_key": "",  # from AIML_API_KEY
        "model": "gpt-4o-mini",
    },
    LLMBackend.OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",  # from OPENAI_API_KEY
        "model": "gpt-4o-mini",
    },
}


def get_backend() -> LLMBackend:
    raw = os.getenv("LLM_BACKEND", "ollama").lower()
    try:
        return LLMBackend(raw)
    except ValueError:
        return LLMBackend.OLLAMA


def resolve_llm_config() -> tuple[str, str, str]:
    """Return (base_url, api_key, model)."""
    backend = get_backend()
    defaults = BACKEND_DEFAULTS[backend]

    base_url = os.getenv("OPENAI_API_BASE") or os.getenv("LLM_BASE_URL") or defaults["base_url"]
    model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or defaults["model"]

    api_key = os.getenv("OPENAI_API_KEY") or defaults["api_key"]
    if backend == LLMBackend.FEATHERLESS:
        api_key = os.getenv("FEATHERLESS_API_KEY") or api_key
    elif backend == LLMBackend.HUGGINGFACE:
        api_key = (
            os.getenv("HF_TOKEN")
            or os.getenv("HUGGINGFACE_API_KEY")
            or os.getenv("HF_API_KEY")
            or os.getenv("VITE_HF_API_KEY")
            or api_key
        )
    elif backend == LLMBackend.AIML_API:
        api_key = os.getenv("AIML_API_KEY") or api_key
    elif backend == LLMBackend.OPENAI:
        api_key = os.getenv("OPENAI_API_KEY") or api_key

    if not api_key or api_key == "":
        raise ValueError(
            f"LLM_BACKEND={backend.value} requires an API key. "
            f"Set the env var shown in .env.example for that backend."
        )

    return base_url, api_key, model


def create_langgraph_adapter(
    custom_instructions: str,
    additional_tools: list | None = None,
) -> LangGraphAdapter:
    """LangGraph adapter using any OpenAI-compatible endpoint (OSS-friendly)."""
    base_url, api_key, model = resolve_llm_config()
    llm = ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=0.2,
    )
    kwargs: dict = {
        "llm": llm,
        "checkpointer": InMemorySaver(),
        "custom_section": custom_instructions,
    }
    if additional_tools:
        kwargs["additional_tools"] = additional_tools
    return LangGraphAdapter(**kwargs)
