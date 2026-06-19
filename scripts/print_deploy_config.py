#!/usr/bin/env python3
"""Log non-secret deploy config at startup (Render debugging)."""
from __future__ import annotations

import os

from shared.band_client.config import resolve_agent_config_path
from shared.band_client.orchestrator import (
    _specialist_complete_cooldown_sec,
    _specialist_stagger_sec,
)
from shared.llm.backends import get_backend, resolve_llm_config


def main() -> None:
    backend = get_backend()
    base_url, _, model = resolve_llm_config()
    cfg_path = resolve_agent_config_path()
    print("=== PermitOS deploy config ===")
    print(f"  LLM_BACKEND={backend.value}")
    print(f"  LLM_MODEL={model}")
    print(f"  OPENAI_API_BASE={base_url}")
    print(f"  LLM_MAX_TOKENS={os.getenv('LLM_MAX_TOKENS', '4096')}")
    print(f"  LLM_MAX_RETRIES={os.getenv('LLM_MAX_RETRIES', '8' if backend.value == 'baseten' else '4')}")
    print(f"  PERMITOS_ORCHESTRATION={os.getenv('PERMITOS_ORCHESTRATION', 'auto')}")
    print(f"  SPECIALIST_STAGGER_SEC={_specialist_stagger_sec():.0f}")
    print(f"  SPECIALIST_COMPLETE_COOLDOWN_SEC={_specialist_complete_cooldown_sec():.0f}")
    print(f"  BAND_ORCHESTRATION_TIMEOUT={os.getenv('BAND_ORCHESTRATION_TIMEOUT', '600')}")
    print(f"  agent_config={cfg_path or 'env/inline'}")
    print(f"  AGENT_CONFIG_PATH={os.getenv('AGENT_CONFIG_PATH', '(not set)')}")
    print("==============================")


if __name__ == "__main__":
    main()
