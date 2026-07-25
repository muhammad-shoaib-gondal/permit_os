"""ZenMux-only LLM integration."""

from shared.llm.zenmux import (
    chat_completion,
    create_chat_model,
    extract_pdf_text,
    resolve_zenmux_config,
)

__all__ = [
    "chat_completion",
    "create_chat_model",
    "extract_pdf_text",
    "resolve_zenmux_config",
]
