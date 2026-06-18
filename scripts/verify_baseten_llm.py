#!/usr/bin/env python3
"""Quick test: Baseten Model API (OpenAI-compatible gpt-oss-120b)."""

from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    import httpx

    from shared.llm.backends import get_backend, resolve_llm_config

    if get_backend().value != "baseten":
        print("Set LLM_BACKEND=baseten in .env")
        sys.exit(1)

    base_url, api_key, model = resolve_llm_config()
    print(f"Testing {model} via {base_url} ...")
    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: PermitOS Baseten OK"}],
            "max_tokens": int(__import__("os").getenv("LLM_MAX_TOKENS", "512")),
            "temperature": 0.2,
        },
        timeout=120.0,
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code >= 400:
        print(resp.text[:500])
        sys.exit(1)
    msg = resp.json()["choices"][0]["message"]
    content = msg.get("content") or msg.get("reasoning_content") or ""
    print(f"Response: {content}")


if __name__ == "__main__":
    main()
