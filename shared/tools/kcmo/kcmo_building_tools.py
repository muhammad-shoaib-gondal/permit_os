from __future__ import annotations

from shared.schemas.kcmo_intake import FindingStatus, KcmoFinding, KcmoIntake
from shared.tools.kcmo.load import load_kcmo_json


def check_kcmo_building(intake: KcmoIntake) -> list[KcmoFinding]:
    pack = load_kcmo_json("building_rules.json")
    assert isinstance(pack, dict)
    findings: list[KcmoFinding] = []

    findings.append(
        KcmoFinding(
            status=FindingStatus.WARN,
            module="building",
            finding="Building permit application expected for regulated work",
            explanation="KCMO requires permit applications for new construction, additions, alterations, repairs, demolition, and occupancy changes as applicable.",
            citation="KCMO Development Process Guide / Chapter 18",
            source_type="code",
            next_action="Prepare IB100 or IB110 submittal package for CompassKC.",
        )
    )

    if intake.stories is None:
        findings.append(
            KcmoFinding(
                status=FindingStatus.DATA_GAP,
                module="building",
                finding="Number of stories missing",
                explanation="Stories are needed for height/egress scoping.",
                citation="IB100 / IB110",
                required_user_data=["Number of stories"],
            )
        )
    if intake.building_area_sqft is None:
        findings.append(
            KcmoFinding(
                status=FindingStatus.DATA_GAP,
                module="building",
                finding="Building area missing",
                explanation="Building area supports plan-review scoping and fee estimation.",
                citation="IB100 / IB110",
                required_user_data=["Building area (sq ft)"],
            )
        )

    if intake.includes_fire_sprinkler_alarm or intake.sprinklered == "yes":
        findings.append(
            KcmoFinding(
                status=FindingStatus.WARN,
                module="fire",
                finding="Fire protection permit review indicated",
                explanation="Fire sprinkler/alarm work is in scope — follow IB116.",
                citation="IB116",
                source_type="information_bulletin",
            )
        )
    elif intake.sprinklered == "unknown":
        findings.append(
            KcmoFinding(
                status=FindingStatus.DATA_GAP,
                module="fire",
                finding="Sprinklered status unknown",
                explanation="Confirm whether the building is sprinklered and whether IB116 applies.",
                citation="IB116",
                required_user_data=["Sprinklered yes/no"],
            )
        )

    if intake.project_category.value == "multifamily":
        findings.append(
            KcmoFinding(
                status=FindingStatus.WARN,
                module="fire",
                finding="Multifamily firewall / fire-separation review",
                explanation="Include IB142 multifamily firewall construction documentation as applicable.",
                citation="IB142",
                source_type="information_bulletin",
            )
        )

    return findings
