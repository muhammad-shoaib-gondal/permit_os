"""OpenAI-compatible LLM backends (Baseten, Groq, Ollama, etc.)."""

from __future__ import annotations

import os
from enum import Enum


class LLMBackend(str, Enum):
    OLLAMA = "ollama"
    OLLAMAFREEAPI = "ollamafreeapi"
    FEATHERLESS = "featherless"
    HUGGINGFACE = "huggingface"
    CEREBRAS = "cerebras"
    BASETEN = "baseten"
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
    LLMBackend.BASETEN: {
        "base_url": "https://inference.baseten.co/v1",
        "api_key": "",  # from BASETEN_API_KEY
        "model": "openai/gpt-oss-120b",
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
    elif backend == LLMBackend.BASETEN:
        api_key = os.getenv("BASETEN_API_KEY") or api_key
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
    """Short user-facing message when analysis does not complete."""
    return "Something went wrong — we couldn't complete the analysis."


def _build_chat_openai(**llm_kwargs):
    """ChatOpenAI with optional cross-process rate limiting for strict providers."""
    from langchain_openai import ChatOpenAI

    from shared.llm.rate_limit import cross_process_llm_lock_enabled, llm_request_slot

    backend = get_backend()
    if backend not in {LLMBackend.BASETEN, LLMBackend.CEREBRAS} or not cross_process_llm_lock_enabled():
        return ChatOpenAI(**llm_kwargs)

    class RateLimitedChatOpenAI(ChatOpenAI):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            with llm_request_slot():
                return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
            with llm_request_slot():
                return await super()._agenerate(
                    messages, stop=stop, run_manager=run_manager, **kwargs
                )

    return RateLimitedChatOpenAI(**llm_kwargs)


