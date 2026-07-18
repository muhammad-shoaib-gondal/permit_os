from __future__ import annotations

from typing import Any

from shared.schemas.kcmo_intake import KcmoIntake
from shared.tools.kcmo.load import load_kcmo_json


def estimate_kcmo_fees(intake: KcmoIntake) -> dict[str, Any]:
    rules = load_kcmo_json("fee_rules.json")
    assert isinstance(rules, dict)
    warnings = list(rules.get("notes") or [])
    warnings.append("Final fees must be confirmed in CompassKC.")

    valuation = intake.estimated_valuation_usd
    if valuation is None or valuation <= 0:
        return {
            "estimate_status": "data_gap",
            "line_items": [],
            "warnings": warnings
            + ["Estimated construction valuation is required for a numeric fee estimate."],
            "required_user_data": ["Estimated construction valuation"],
        }

    # MVP: without full Chapter 18 tables, return structured rough placeholder only.
    # Do not invent a fake building-permit fee from valuation.
    return {
        "estimate_status": "data_gap",
        "line_items": [
            {
                "label": "Plan check fee",
                "amount": None,
                "basis": (
                    "KCMO describes plan check fee as one-half of the total building permit fee, "
                    "paid when plans are submitted. Exact building-permit fee tables are not fully encoded yet."
                ),
                "source": "KCMO Development Guide / Chapter 18",
            }
        ],
        "warnings": warnings
        + [
            f"Valuation provided (${valuation:,}) but Chapter 18 fee schedule formulas are not fully encoded in this MVP.",
            "Use KCMO permit / plan-check / site-disturbance calculators for official amounts.",
        ],
        "valuation_usd": valuation,
        "project_category": intake.project_category.value,
        "scope_type": intake.scope_type.value,
    }
