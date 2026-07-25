#!/usr/bin/env python3
"""Verify the EstatePermit ZenMux model configuration with one live request."""

from __future__ import annotations

import sys

import httpx
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    from shared.llm.zenmux import resolve_zenmux_config

    try:
        config = resolve_zenmux_config()
    except ValueError as exc:
        print(exc)
        sys.exit(1)

    print(f"Testing {config.model} via {config.base_url} ...")
    response = httpx.post(
        f"{config.base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.model,
            "messages": [
                {"role": "user", "content": "Reply with exactly: EstatePermit ZenMux OK"}
            ],
            "max_tokens": 64,
        },
        timeout=config.timeout_seconds,
    )
    print(f"Status: {response.status_code}")
    if response.status_code >= 400:
        print(response.text[:500])
        sys.exit(1)
    print(f"Response: {response.json()['choices'][0]['message']['content']}")


if __name__ == "__main__":
    main()
