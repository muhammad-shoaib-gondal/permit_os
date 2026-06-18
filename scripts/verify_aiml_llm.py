#!/usr/bin/env python3
"""Quick test: AI/ML API (OpenAI-compatible)."""

from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    import httpx

    from shared.llm.backends import resolve_llm_config

    base_url, api_key, model = resolve_llm_config()
    if not api_key:
        print("Set AIML_API_KEY in .env")
        sys.exit(1)

    print(f"Testing {model} via {base_url} ...")
    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: PermitOS AIML OK"}],
            "max_tokens": 32,
        },
        timeout=60.0,
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code >= 400:
        print(resp.text[:400])
        sys.exit(1)
    content = resp.json()["choices"][0]["message"]["content"]
    print(f"Response: {content}")


if __name__ == "__main__":
    main()
