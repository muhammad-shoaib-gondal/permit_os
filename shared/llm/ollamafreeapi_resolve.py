"""Resolve a reachable community Ollama server via the ollamafreeapi package."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

_CACHE: dict[str, Any] | None = None
_CACHE_AT: float = 0.0

_MODEL_PREFERENCES = (
    "llama3.2:latest",
    "llama3.2:3b",
    "llama3:latest",
    "mistral:latest",
    "smollm2:135m",
)


def _cache_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / ".ollamafreeapi_cache.json"


def _normalize_host(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = f"http://{url}"
    return url


def _openai_base(host: str) -> str:
    return f"{_normalize_host(host)}/v1"


def _pick_model(available: list[str], preferred: str | None) -> str | None:
    if preferred and preferred in available:
        return preferred
    lower = {m.lower(): m for m in available}
    if preferred:
        pref = preferred.lower()
        for name in available:
            if pref in name.lower() or name.lower() in pref:
                return name
        if pref in lower:
            return lower[pref]
    for candidate in _MODEL_PREFERENCES:
        if candidate in available:
            return candidate
        for name in available:
            if candidate.split(":")[0] in name.lower():
                return name
    return available[0] if available else None


def _probe_server(host: str, preferred_model: str | None, timeout: float) -> tuple[str, str] | None:
    host = _normalize_host(host)
    try:
        resp = httpx.get(f"{host}/api/tags", timeout=timeout)
        resp.raise_for_status()
        available = [m["name"] for m in resp.json().get("models", []) if m.get("name")]
    except Exception:
        return None
    model = _pick_model(available, preferred_model)
    if not model:
        return None
    try:
        test = httpx.post(
            f"{host}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "max_tokens": 8,
            },
            timeout=timeout,
        )
        if test.status_code >= 400:
            return None
    except Exception:
        return None
    return _openai_base(host), model


def _load_disk_cache() -> dict[str, Any] | None:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("base_url") and data.get("model"):
            return data
    except Exception:
        pass
    return None


def _save_disk_cache(base_url: str, model: str, host: str) -> None:
    try:
        _cache_path().write_text(
            json.dumps(
                {"base_url": base_url, "model": model, "host": host, "saved_at": time.time()},
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def _iter_catalog_hosts() -> list[str]:
    from ollamafreeapi import OllamaFreeAPI

    api = OllamaFreeAPI()
    hosts: list[tuple[float, str]] = []
    seen: set[str] = set()
    for model in api.list_models():
        for server in api.get_model_servers(model):
            host = server.get("url") or ""
            if not host or host in seen:
                continue
            seen.add(host)
            perf = server.get("performance") or {}
            tok = perf.get("tokens_per_second")
            score = float(tok) if isinstance(tok, (int, float)) else 0.0
            hosts.append((score, host))
    hosts.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in hosts]


def resolve_ollamafreeapi() -> tuple[str, str]:
    """Return (openai_base_url, model) for a reachable community Ollama node."""
    global _CACHE, _CACHE_AT

    ttl = float(os.getenv("OLLAMAFREEAPI_CACHE_TTL_SEC", "900"))
    preferred_model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL")
    timeout = float(os.getenv("OLLAMAFREEAPI_PROBE_TIMEOUT_SEC", "20"))

    pinned_host = os.getenv("OLLAMAFREEAPI_BASE_URL") or os.getenv("OLLAMAFREEAPI_HOST")
    if pinned_host:
        host = _normalize_host(pinned_host)
        probed = _probe_server(host, preferred_model, timeout)
        if probed:
            base_url, model = probed
            _CACHE = {"base_url": base_url, "model": model, "host": host}
            _CACHE_AT = time.monotonic()
            _save_disk_cache(base_url, model, host)
            return base_url, model
        raise RuntimeError(
            f"OLLAMAFREEAPI_BASE_URL={host} is unreachable or model unavailable. "
            "Try another host from the catalog or set LLM_MODEL."
        )

    if _CACHE and (time.monotonic() - _CACHE_AT) < ttl:
        return _CACHE["base_url"], _CACHE["model"]

    disk = _load_disk_cache()
    if disk and (time.time() - float(disk.get("saved_at", 0))) < ttl:
        host = disk.get("host") or disk["base_url"].removesuffix("/v1")
        probed = _probe_server(host, preferred_model or disk.get("model"), timeout)
        if probed:
            base_url, model = probed
            _CACHE = {"base_url": base_url, "model": model, "host": host}
            _CACHE_AT = time.monotonic()
            return base_url, model

    last_error = "no community servers responded"
    for host in _iter_catalog_hosts():
        probed = _probe_server(host, preferred_model, timeout)
        if probed:
            base_url, model = probed
            _CACHE = {"base_url": base_url, "model": model, "host": _normalize_host(host)}
            _CACHE_AT = time.monotonic()
            _save_disk_cache(base_url, model, _normalize_host(host))
            return base_url, model
        last_error = f"failed probing {host}"

    raise RuntimeError(
        "OllamaFreeAPI: no reachable community Ollama servers from the catalog. "
        f"Last: {last_error}. Pin a host in .env: OLLAMAFREEAPI_BASE_URL=http://host:11434"
    )
