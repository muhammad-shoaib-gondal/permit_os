"""LangChain tools — Austin knowledge exposed to Band agents."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from shared.schemas.project_brief import ProjectBrief
from shared.tools import building_tools, jurisdiction_tools, site_tools
from shared.tools.knowledge import load_json


@tool
def lookup_jurisdiction(address: str) -> str:
    """Resolve city/county/zoning district for an address. Use for Austin TX projects."""
    return json.dumps(jurisdiction_tools.lookup_jurisdiction(address))


@tool
def get_zoning_rules(city: str, district: str) -> str:
    """Get zoning rules for a district (e.g. MF-3 in Austin)."""
    return json.dumps(jurisdiction_tools.get_zoning_rules(city, district))


@tool
def calculate_setbacks(block_id: str, side: str, actual_ft: float, district: str = "MF-3") -> str:
    """Compare actual setback vs required for a building block."""
    brief = ProjectBrief(
        project_name="tool",
        address="Austin, TX",
        units=1,
        stories=1,
        gross_sqft=1000,
        lot_sqft=5000,
        parking_spaces=1,
        blocks=[
            __import__("shared.schemas.project_brief", fromlist=["BlockSetback"]).BlockSetback(
                block_id=block_id, side=side, required_ft=0, actual_ft=actual_ft
            )
        ],
    )
    results = jurisdiction_tools.calculate_setbacks(brief, district)
    return json.dumps(results)


@tool
def check_egress(units: int, stories: int) -> str:
    """Pre-screen egress requirements for multifamily."""
    return json.dumps(building_tools.check_egress_requirements(units, stories))


@tool
def check_sprinklers(stories: int) -> str:
    """Check if sprinklers are required by story count."""
    return json.dumps(building_tools.check_sprinkler_requirements(stories))


@tool
def check_accessibility(unit_count: int) -> str:
    """Check Type B accessible unit requirements."""
    return json.dumps(building_tools.check_accessibility_requirements(unit_count))


@tool
def lookup_flood_zone(address: str) -> str:
    """FEMA flood zone lookup for site address."""
    return json.dumps(site_tools.lookup_flood_zone(address))


@tool
def get_utility_requirements(units: int) -> str:
    """Water/sewer capacity screening thresholds."""
    return json.dumps(site_tools.get_utility_requirements(units))


@tool
def get_fee_schedule() -> str:
    """Austin permit fee schedule for estimates."""
    return json.dumps(load_json("fee_schedule.json"))


@tool
def get_permit_catalog() -> str:
    """Austin permit types, agencies, and dependencies."""
    return json.dumps(load_json("permit_catalog.json"))


JURISDICTION_TOOLS = [lookup_jurisdiction, get_zoning_rules, calculate_setbacks]
BUILDING_TOOLS = [check_egress, check_sprinklers, check_accessibility]
SITE_TOOLS = [lookup_flood_zone, get_utility_requirements]
PACKAGER_TOOLS = [get_fee_schedule, get_permit_catalog]
CONDUCTOR_TOOLS: list = []

TOOLS_BY_ROLE = {
    "conductor": CONDUCTOR_TOOLS,
    "jurisdiction": JURISDICTION_TOOLS,
    "building": BUILDING_TOOLS,
    "site": SITE_TOOLS,
    "packager": PACKAGER_TOOLS,
}
