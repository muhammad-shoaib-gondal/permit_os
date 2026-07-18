from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from shared.tools.kcmo.validate_pack import kcmo_pack_root


@lru_cache(maxsize=32)
def load_kcmo_json(name: str) -> dict[str, Any] | list[Any]:
    path = kcmo_pack_root() / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def catalog_by_id() -> dict[str, dict[str, Any]]:
    catalog = load_kcmo_json("permit_catalog.json")
    assert isinstance(catalog, dict)
    return {p["id"]: p for p in catalog.get("permit_types", [])}
