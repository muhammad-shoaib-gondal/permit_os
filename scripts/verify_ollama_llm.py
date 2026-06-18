#!/usr/bin/env python3
"""Quick test: Ollama (local or remote e.g. Railway)."""

from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    import httpx

    from shared.llm.backends import get_backend, resolve_llm_config

    if get_backend().value != "ollama":
        print("Set LLM_BACKEND=ollama in .env")
        sys.exit(1)

    base_url, api_key, model = resolve_llm_config()
    print(f"Testing {model} via {base_url} ...")

    tags = httpx.get(
        base_url.replace("/v1", "") + "/api/tags",
        timeout=30.0,
    )
    available = [m["name"] for m in tags.json().get("models", [])]
    print(f"Models on server: {available or '(none — run ollama pull on the host)'}")
    if model not in available and available:
        print(f"Warning: {model} not in list; server may reject requests.")

    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: PermitOS Ollama OK"}],
            "max_tokens": 24,
        },
        timeout=180.0,
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code >= 400:
        print(resp.text[:500])
        sys.exit(1)
    content = resp.json()["choices"][0]["message"]["content"]
    print(f"Response: {content}")


if __name__ == "__main__":
    main()
