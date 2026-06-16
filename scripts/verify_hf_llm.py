#!/usr/bin/env python3
"""Quick test: Hugging Face Inference (OpenAI-compatible router)."""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()


async def main() -> None:
    import httpx

    key = (
        os.getenv("HF_TOKEN")
        or os.getenv("HF_API_KEY")
        or os.getenv("VITE_HF_API_KEY")
    )
    model = os.getenv("LLM_MODEL", "meta-llama/Llama-3.2-3B-Instruct")
    base = os.getenv("OPENAI_API_BASE", "https://router.huggingface.co/v1")

    if not key:
        print("Set HF_TOKEN in .env")
        sys.exit(1)

    print(f"Testing {model} via {base} ...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{base.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "Reply with exactly: PermitOS HF OK"}
                ],
                "max_tokens": 32,
            },
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code >= 400:
            print(resp.text)
            sys.exit(1)
        content = resp.json()["choices"][0]["message"]["content"]
        print(f"Response: {content}")
        print("Hugging Face LLM ready for Band agents.")


if __name__ == "__main__":
    asyncio.run(main())
