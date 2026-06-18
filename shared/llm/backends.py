"""OpenAI-compatible LLM backends for Band agents (Ollama, Featherless, Hugging Face)."""

from __future__ import annotations

import os
from enum import Enum

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from band.adapters import LangGraphAdapter


class LLMBackend(str, Enum):
    OLLAMA = "ollama"
    OLLAMAFREEAPI = "ollamafreeapi"
    FEATHERLESS = "featherless"
    HUGGINGFACE = "huggingface"
    CEREBRAS = "cerebras"
    GROQ = "groq"
    CURSOR = "cursor"
    OPENAI = "openai"
    AIML_API = "aiml_api"


BACKEND_DEFAULTS: dict[LLMBackend, dict[str, str]] = {
    LLMBackend.OLLAMA: {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "llama3.2",
    },
    LLMBackend.OLLAMAFREEAPI: {
        "base_url": "",  # resolved at runtime via ollamafreeapi package
        "api_key": "ollama",
        "model": "llama3.2:latest",
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
    LLMBackend.CEREBRAS: {
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": "",  # from CEREBRAS_API_KEY
        "model": "gpt-oss-120b",
    },
    LLMBackend.GROQ: {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "",  # from GROQ_API_KEY
        "model": "llama-3.3-70b-versatile",
    },
    LLMBackend.CURSOR: {
        "base_url": "http://127.0.0.1:8787/v1",
        "api_key": "local",  # proxy auth; real key is CURSOR_API_KEY on the proxy process
        "model": "composer-2.5",
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
    elif backend == LLMBackend.CEREBRAS:
        api_key = os.getenv("CEREBRAS_API_KEY") or api_key
    elif backend == LLMBackend.GROQ:
        api_key = os.getenv("GROQ_API_KEY") or api_key
    elif backend == LLMBackend.OLLAMAFREEAPI:
        from shared.llm.ollamafreeapi_resolve import resolve_ollamafreeapi

        if os.getenv("OPENAI_API_BASE") or os.getenv("LLM_BASE_URL"):
            base_url = os.getenv("OPENAI_API_BASE") or os.getenv("LLM_BASE_URL") or base_url
        else:
            base_url, discovered_model = resolve_ollamafreeapi()
            if not os.getenv("LLM_MODEL") and not os.getenv("OPENAI_MODEL"):
                model = discovered_model
        api_key = "ollama"
    elif backend == LLMBackend.CURSOR:
        base_url = (
            os.getenv("CURSOR_OPENAI_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
            or base_url
        )
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("CURSOR_PROXY_AUTH_KEY") or api_key
        if not os.getenv("CURSOR_API_KEY"):
            raise ValueError(
                "LLM_BACKEND=cursor requires CURSOR_API_KEY in .env for the local proxy. "
                "Start it with: scripts/start_cursor_proxy.ps1"
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


def orchestration_hint() -> str:
    """User-facing hint when Band orchestration times out."""
    from shared.llm.backends import LLMBackend, get_backend

    backend = get_backend()
    if backend == LLMBackend.CEREBRAS:
        return (
            "Cerebras free tier rate-limits requests (429 in agent logs). "
            "Wait 1–2 minutes and retry, or set LLM_BACKEND=groq in .env."
        )
    if backend == LLMBackend.GROQ:
        return (
            "Groq rate limits (429) or key issue. Check GROQ_API_KEY and agent logs."
        )
    if backend == LLMBackend.OLLAMAFREEAPI:
        return (
            "OllamaFreeAPI community server unreachable. Set OLLAMAFREEAPI_BASE_URL in .env "
            "or run: python scripts/verify_ollamafreeapi_llm.py"
        )
    if backend == LLMBackend.CURSOR:
        return (
            "Cursor Composer proxy not responding. Run scripts/start_cursor_proxy.ps1 "
            "and ensure CURSOR_API_KEY is set in .env."
        )
    if backend == LLMBackend.HUGGINGFACE:
        return (
            "Hugging Face credits may be depleted (402). "
            "Switch LLM_BACKEND=cerebras or ollama in .env."
        )
    return "Ensure all 5 agents are running: scripts/start_all_agents.ps1"


def create_langgraph_adapter(
    custom_instructions: str,
    additional_tools: list | None = None,
) -> LangGraphAdapter:
    """LangGraph adapter using any OpenAI-compatible endpoint (OSS-friendly)."""
    base_url, api_key, model = resolve_llm_config()
    llm_kwargs: dict = {
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "temperature": 0.2,
    }
    # gpt-oss-120b emits reasoning tokens; needs headroom for actual content.
    if get_backend() in {LLMBackend.CEREBRAS, LLMBackend.OLLAMAFREEAPI}:
        llm_kwargs["max_tokens"] = int(os.getenv("LLM_MAX_TOKENS", "4096"))
        llm_kwargs["max_retries"] = int(os.getenv("LLM_MAX_RETRIES", "4"))
    if get_backend() == LLMBackend.OLLAMAFREEAPI:
        llm_kwargs["request_timeout"] = float(os.getenv("OLLAMAFREEAPI_REQUEST_TIMEOUT_SEC", "120"))
    if get_backend() == LLMBackend.OLLAMA and "localhost" not in base_url and "127.0.0.1" not in base_url:
        llm_kwargs["request_timeout"] = float(os.getenv("OLLAMA_REQUEST_TIMEOUT_SEC", "180"))
        llm_kwargs["max_retries"] = int(os.getenv("LLM_MAX_RETRIES", "3"))
    llm = ChatOpenAI(**llm_kwargs)
    kwargs: dict = {
        "llm": llm,
        "checkpointer": InMemorySaver(),
        "custom_section": custom_instructions,
    }
    if additional_tools:
        kwargs["additional_tools"] = additional_tools
    return LangGraphAdapter(**kwargs)
