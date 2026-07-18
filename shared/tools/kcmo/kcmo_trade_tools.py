from __future__ import annotations

from shared.schemas.kcmo_intake import FindingStatus, KcmoFinding, KcmoIntake, ProjectCategory
from shared.tools.kcmo.load import load_kcmo_json


def check_kcmo_trade_permits(intake: KcmoIntake) -> list[KcmoFinding]:
    trade = load_kcmo_json("trade_permits.json")
    assert isinstance(trade, dict)
    rules = trade.get("rules") or {}
    findings: list[KcmoFinding] = []

    def add(status: FindingStatus, finding: str, explanation: str, citation: str, next_action: str = "") -> None:
        findings.append(
            KcmoFinding(
                status=status,
                module="trade",
                finding=finding,
                explanation=explanation,
                citation=citation,
                source_type="official_guide",
                next_action=next_action,
            )
        )

    any_trade = intake.includes_electrical or intake.includes_plumbing or intake.includes_mechanical
    if intake.includes_electrical:
        add(
            FindingStatus.WARN,
            "Electrical Permit likely required",
            "Intake indicates electrical work. KCMO requires permits before most electrical work.",
            "KCMO Electrical, Plumbing and Mechanical Permits",
            "Add Electrical Permit to the working bundle if not already present.",
        )
    if intake.includes_plumbing:
        add(
            FindingStatus.WARN,
            "Plumbing Permit likely required",
            "Intake indicates plumbing work.",
            "KCMO Electrical, Plumbing and Mechanical Permits",
        )
    if intake.includes_mechanical:
        add(
            FindingStatus.WARN,
            "Mechanical/HVAC Permit likely required",
            "Intake indicates mechanical/HVAC work.",
            "KCMO Electrical, Plumbing and Mechanical Permits",
        )
    if not any_trade:
        add(
            FindingStatus.PASS,
            "No trade work selected",
            "Electrical/plumbing/mechanical flags are off. Update intake if trade work is planned.",
            "KCMO trade permits guidance",
        )

    category = intake.project_category.value
    if category in rules.get("trade_depends_on_building_permit_for", []) and any_trade:
        add(
            FindingStatus.WARN,
            "Trade permits may wait on building permit approval",
            "For multifamily and commercial projects, trade permits are typically issued only after building plans are approved and the building permit is issued.",
            "KCMO Electrical, Plumbing and Mechanical Permits",
            "Sequence trade filings after building permit issuance unless Express/limited paths apply.",
        )

    if category in ("multifamily", "commercial") or intake.dwelling_type == "two_family":
        add(
            FindingStatus.WARN,
            "Licensed contractor required for trade permits",
            "KCMO states permits for two-family, multifamily, and commercial buildings may be issued only to licensed contractors.",
            "KCMO Electrical, Plumbing and Mechanical Permits",
        )

    if intake.project_category == ProjectCategory.SINGLE_FAMILY and intake.owner_occupied:
        add(
            FindingStatus.WARN,
            "Homeowner-occupant exception may apply",
            "Single-family homeowner occupants may be issued permits for their own work on their personal permanent residence — verify IB146.",
            "IB146",
            "Confirm homeowner-occupant affidavit eligibility before assuming contractor exemption.",
        )

    return findings
