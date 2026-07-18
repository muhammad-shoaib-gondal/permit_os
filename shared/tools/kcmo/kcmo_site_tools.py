from __future__ import annotations

from shared.schemas.kcmo_intake import FindingStatus, FloodplainStatus, KcmoFinding, KcmoIntake
from shared.tools.kcmo.load import load_kcmo_json


def check_kcmo_floodplain(intake: KcmoIntake) -> KcmoFinding:
    rules = load_kcmo_json("site_floodplain_rules.json")
    assert isinstance(rules, dict)
    by_id = {r["id"]: r for r in rules.get("rules", [])}

    if intake.floodplain_status == FloodplainStatus.YES:
        r = by_id["floodplain_permit_if_mapped"]
        return KcmoFinding(
            status=FindingStatus.WARN,
            module="site",
            finding=r["finding"],
            explanation=r["explanation"],
            citation=r["citation"],
            source_type="information_bulletin",
            next_action="Prepare Floodplain Development Permit Application (IB120).",
        )
    if intake.floodplain_status == FloodplainStatus.UNKNOWN:
        r = by_id["floodplain_unknown"]
        return KcmoFinding(
            status=FindingStatus.DATA_GAP,
            module="site",
            finding=r["finding"],
            explanation=r["explanation"],
            citation=r["citation"],
            source_type="information_bulletin",
            required_user_data=["Floodplain yes/no confirmation"],
            next_action="Check Parcel Viewer / floodplain maps and update intake.",
        )
    return KcmoFinding(
        status=FindingStatus.PASS,
        module="site",
        finding="No mapped floodplain trigger from intake",
        explanation="Intake marks floodplain as no. Re-verify if site plans show floodplain constraints.",
        citation="Chapter 28 / IB120",
        source_type="code",
    )


def check_kcmo_right_of_way_impacts(intake: KcmoIntake) -> list[KcmoFinding]:
    rules = load_kcmo_json("site_floodplain_rules.json")
    assert isinstance(rules, dict)
    row_rule = next(r for r in rules["rules"] if r["id"] == "row_impacts")
    if intake.affects_public_row or intake.driveway_work:
        return [
            KcmoFinding(
                status=FindingStatus.WARN,
                module="site",
                finding=row_rule["finding"],
                explanation=row_rule["explanation"],
                citation=row_rule["citation"],
                source_type="official_guide",
                next_action="Coordinate curb/sidewalk/driveway/ROW permits with Public Works as applicable.",
            )
        ]
    return [
        KcmoFinding(
            status=FindingStatus.PASS,
            module="site",
            finding="No ROW / driveway impacts selected",
            explanation="Update intake if work affects curb, sidewalk, driveway approach, sewer, or stormwater in the ROW.",
            citation=row_rule["citation"],
            source_type="official_guide",
        )
    ]


def check_kcmo_public_improvements(intake: KcmoIntake) -> list[KcmoFinding]:
    rules = load_kcmo_json("site_floodplain_rules.json")
    assert isinstance(rules, dict)
    pi = next(r for r in rules["rules"] if r["id"] == "public_improvements")
    if intake.affects_public_row and intake.project_category.value in ("commercial", "multifamily"):
        return [
            KcmoFinding(
                status=FindingStatus.WARN,
                module="site",
                finding=pi["finding"],
                explanation=pi["explanation"],
                citation=pi["citation"],
                source_type="official_guide",
            )
        ]
    return []


def run_kcmo_site_checks(intake: KcmoIntake) -> list[KcmoFinding]:
    findings = [check_kcmo_floodplain(intake)]
    findings.extend(check_kcmo_right_of_way_impacts(intake))
    findings.extend(check_kcmo_public_improvements(intake))
    return findings
