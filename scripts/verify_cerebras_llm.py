#!/usr/bin/env python3
"""Quick test: Cerebras Inference (OpenAI-compatible)."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    import httpx

    from shared.llm.backends import resolve_llm_config

    base_url, api_key, model = resolve_llm_config()
    if not api_key:
        print("Set CEREBRAS_API_KEY in .env")
        sys.exit(1)

    print(f"Testing {model} via {base_url} ...")
    for try_model in (model, "gpt-oss-120b", "llama3.1-8b"):
        resp = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": try_model,
                "messages": [{"role": "user", "content": "Reply with exactly: PermitOS Cerebras OK"}],
                "max_tokens": 32,
            },
            timeout=60.0,
        )
        print(f"  {try_model}: {resp.status_code}")
        if resp.status_code < 400:
            msg = resp.json()["choices"][0]["message"]
            content = msg.get("content") or msg.get("reasoning") or str(msg)
            print(f"  Response: {content}")
            print(f"Use LLM_MODEL={try_model}")
            return
        print(f"  {resp.text[:200]}")
    sys.exit(1)


if __name__ == "__main__":
    main()
