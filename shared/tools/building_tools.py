from __future__ import annotations

from shared.tools.knowledge import load_json


def get_building_code_rules(city: str, project_type: str) -> list[dict]:
    return load_json("building_code_snippets/snippets.json")


def check_egress_requirements(units: int, stories: int) -> dict:
    snippets = load_json("building_code_snippets/snippets.json")
    egress = next(s for s in snippets if s["id"] == "egress")
    required = stories >= 4 or units >= 16
    return {
        "status": "pass" if required else "warn",
        "rule": "Two remote exits required",
        "citation": egress["citation"],
        "detail": f"{units} units, {stories} stories — dual egress paths required",
    }


def check_sprinkler_requirements(stories: int) -> dict:
    snippets = load_json("building_code_snippets/snippets.json")
    sprinkler = next(s for s in snippets if s["id"] == "sprinkler_multifamily")
    required = stories >= 4
    return {
        "status": "pass" if required else "warn",
        "rule": "Automatic sprinkler system required",
        "citation": sprinkler["citation"],
        "detail": f"{stories} stories — sprinklers required throughout",
        "recommendation": "Include sprinkler layout in fire protection submittal",
    }


def check_accessibility_requirements(unit_count: int) -> dict:
    snippets = load_json("building_code_snippets/snippets.json")
    acc = next(s for s in snippets if s["id"] == "accessible_units")
    min_units = max(1, int(unit_count * 0.05))
    return {
        "status": "pass",
        "rule": "Type B accessible units",
        "citation": acc["citation"],
        "detail": f"Minimum {min_units} Type B units required for {unit_count} total units",
    }
