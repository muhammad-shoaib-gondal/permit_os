from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

KNOWLEDGE_BASE = Path(__file__).resolve().parents[2] / "knowledge"

JURISDICTION_PATHS: dict[str, Path] = {
    "austin_tx": KNOWLEDGE_BASE / "austin",
    "manhattan_ks": KNOWLEDGE_BASE / "kansas" / "manhattan",
    "seattle_wa": KNOWLEDGE_BASE / "washington" / "seattle",
}

_current_jurisdiction: ContextVar[str] = ContextVar("jurisdiction", default="austin_tx")


def resolve_knowledge_root(jurisdiction: str | None = None) -> Path:
    jid = jurisdiction or _current_jurisdiction.get()
    root = JURISDICTION_PATHS.get(jid)
    if root is None or not root.is_dir():
        raise ValueError(f"Unknown or missing knowledge pack for jurisdiction: {jid}")
    return root


@contextmanager
def jurisdiction_context(jurisdiction: str):
    token = _current_jurisdiction.set(jurisdiction)
    try:
        yield
    finally:
        _current_jurisdiction.reset(token)


def list_jurisdictions() -> list[dict]:
    """Scan knowledge directory for available jurisdiction packs."""
    results: list[dict] = []

    austin = KNOWLEDGE_BASE / "austin"
    if austin.is_dir():
        results.append(
            {
                "id": "austin_tx",
                "label": "Austin, TX",
                "state": "TX",
                "city": "Austin",
                "coverage_status": "active",
            }
        )

    for state_dir in sorted(KNOWLEDGE_BASE.glob("*/")):
        if not state_dir.is_dir() or state_dir.name == "austin":
            continue
        for city_dir in sorted(state_dir.glob("*/")):
            if not city_dir.is_dir() or city_dir.name == "state":
                continue
            meta_path = city_dir / "metadata.json"
            meta: dict = {}
            if meta_path.is_file():
                with meta_path.open(encoding="utf-8") as f:
                    meta = json.load(f)
            jid = meta.get("jurisdiction_id", f"{city_dir.name}-{state_dir.name}").replace("-", "_")
            if jid == "manhattan_ks" or city_dir.name == "manhattan":
                jid = "manhattan_ks"
            results.append(
                {
                    "id": jid,
                    "label": f"{meta.get('city', city_dir.name.title())}, {meta.get('state', state_dir.name.upper())}",
                    "state": meta.get("state", state_dir.name.upper()),
                    "city": meta.get("city", city_dir.name.title()),
                    "coverage_status": meta.get("coverage_status", "available"),
                }
            )

    return results


@lru_cache(maxsize=32)
def _load_json_cached(root_str: str, name: str) -> dict | list:
    path = Path(root_str) / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_json(name: str, jurisdiction: str | None = None) -> dict | list:
    root = resolve_knowledge_root(jurisdiction)
    return _load_json_cached(str(root), name)
