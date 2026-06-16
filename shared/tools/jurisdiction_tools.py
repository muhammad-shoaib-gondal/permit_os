from __future__ import annotations

from shared.schemas.project_brief import ProjectBrief
from shared.tools.knowledge import load_json


def lookup_jurisdiction(address: str) -> dict:
    zoning = load_json("zoning_rules.json")
    demo = zoning.get("demo_addresses", {}).get(address)
    if demo or "Austin, TX" in address:
        district = demo["district"] if demo else "MF-3"
        return {
            "city": "Austin",
            "county": "Travis",
            "state": "TX",
            "district": district,
            "codes_applicable": [
                "Austin Land Development Code",
                "Austin Building Technical Codes",
                "IBC 2021 with local amendments",
            ],
            "demo_mode": demo is None,
        }
    return {
        "city": "Unknown",
        "county": "Unknown",
        "state": "Unknown",
        "district": None,
        "codes_applicable": ["IBC 2021 (generic pre-screen only)"],
        "demo_mode": True,
        "warning": "Address outside Austin MVP — using generic checks",
    }


def get_zoning_rules(city: str, district: str) -> dict:
    zoning = load_json("zoning_rules.json")
    return zoning.get("districts", {}).get(district, {})


def calculate_setbacks(brief: ProjectBrief, district: str) -> list[dict]:
    rules = get_zoning_rules("Austin", district)
    required_side = rules.get("setbacks_ft", {}).get("side", 10)
    results = []
    for block in brief.blocks:
        status = "pass" if block.actual_ft >= required_side else "fail"
        results.append(
            {
                "block_id": block.block_id,
                "side": block.side,
                "required_ft": required_side,
                "actual_ft": block.actual_ft,
                "status": status,
                "citation": load_json("zoning_rules.json")["citations"]["side_setback"],
                "detail": (
                    f"{block.block_id} {block.side} wall at {block.actual_ft}ft "
                    f"(minimum {required_side}ft)"
                ),
            }
        )
    return results
