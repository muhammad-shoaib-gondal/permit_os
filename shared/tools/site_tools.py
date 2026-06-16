from __future__ import annotations

from shared.tools.knowledge import load_json


def lookup_flood_zone(address: str) -> dict:
    env = load_json("environmental_triggers.json")
    zone = env.get("flood_zones", {}).get(address)
    if zone:
        return zone
    return {
        "zone": "X",
        "description": "Assumed minimal flood hazard (demo default)",
        "citation": "FEMA FIRM (demo)",
    }


def get_environmental_triggers(city: str, impervious_sqft: float) -> list[dict]:
    env = load_json("environmental_triggers.json")
    triggers = []
    acre = impervious_sqft / 43560
    for t in env.get("triggers", []):
        if t["id"] == "stormwater" and acre > 0.5:
            triggers.append({**t, "triggered": True})
        else:
            triggers.append({**t, "triggered": False})
    return triggers


def get_utility_requirements(units: int) -> dict:
    util = load_json("utility_requirements.json")
    water = util["water_sewer"]
    return {
        "water_sewer_review": units >= water["capacity_review_threshold_units"],
        "threshold_units": water["capacity_review_threshold_units"],
        "citation": water["citation"],
        "electrical_min_amps": util["electrical"]["multifamily_min_service_amps"],
        "electrical_citation": util["electrical"]["citation"],
    }
