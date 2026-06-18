#!/usr/bin/env python3
"""Quick test: Cursor Composer via local OpenAI-compatible proxy."""

from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    import httpx

    from shared.llm.backends import get_backend, resolve_llm_config

    if get_backend().value != "cursor":
        print("Set LLM_BACKEND=cursor in .env")
        sys.exit(1)

    base_url, api_key, model = resolve_llm_config()
    print(f"Testing {model} via {base_url} ...")
    print("(Ensure scripts/start_cursor_proxy.ps1 is running in another terminal.)")

    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: PermitOS Cursor OK"}],
                "max_tokens": 32,
            },
            timeout=240.0,
        )
    except httpx.ConnectError:
        print("Cannot reach proxy. Start: scripts/start_cursor_proxy.ps1")
        sys.exit(1)

    print(f"Status: {resp.status_code}")
    if resp.status_code >= 400:
        print(resp.text[:500])
        sys.exit(1)
    content = resp.json()["choices"][0]["message"]["content"]
    print(f"Response: {content}")


if __name__ == "__main__":
    main()
