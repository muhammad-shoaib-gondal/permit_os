from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge" / "austin"


@lru_cache
def load_json(name: str) -> dict | list:
    path = KNOWLEDGE_ROOT / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)
