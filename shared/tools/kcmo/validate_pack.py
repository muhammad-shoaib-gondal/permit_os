"""Validate the KCMO knowledge pack at startup / test time."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = [
    "jurisdiction.json",
    "source_index.json",
    "permit_catalog.json",
    "project_type_matrix.json",
    "document_checklists.json",
    "zoning_rules.json",
    "building_rules.json",
    "trade_permits.json",
    "fire_life_safety.json",
    "site_floodplain_rules.json",
    "fee_rules.json",
    "coverage.json",
]

REQUIRED_KEYS: dict[str, list[str]] = {
    "jurisdiction.json": ["jurisdiction_id", "portal_url", "supported_categories"],
    "permit_catalog.json": ["permit_types"],
    "document_checklists.json": ["items"],
    "coverage.json": ["coverage_status", "supported_categories"],
}


def kcmo_pack_root() -> Path:
    return Path(__file__).resolve().parents[3] / "knowledge" / "missouri" / "kansas_city_mo"


def validate_kcmo_knowledge_pack(root: Path | None = None) -> dict[str, Any]:
    pack = root or kcmo_pack_root()
    errors: list[str] = []
    warnings: list[str] = []

    if not pack.is_dir():
        return {
            "ok": False,
            "coverage_status": "preview_only",
            "errors": [f"Missing knowledge pack directory: {pack}"],
            "warnings": [],
        }

    for name in REQUIRED_FILES:
        path = pack / name
        if not path.is_file():
            errors.append(f"Missing required file: {name}")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON in {name}: {exc}")
            continue
        for key in REQUIRED_KEYS.get(name, []):
            if key not in data:
                errors.append(f"{name} missing required key: {key}")

    coverage_status = "active"
    coverage_path = pack / "coverage.json"
    if coverage_path.is_file() and not errors:
        try:
            coverage_status = json.loads(coverage_path.read_text(encoding="utf-8")).get(
                "coverage_status", "active"
            )
        except json.JSONDecodeError:
            pass

    if errors:
        coverage_status = "preview_only"
        warnings.append("KCMO pack validation failed — treat jurisdiction as preview_only.")

    return {
        "ok": not errors,
        "coverage_status": coverage_status,
        "errors": errors,
        "warnings": warnings,
        "root": str(pack),
    }
