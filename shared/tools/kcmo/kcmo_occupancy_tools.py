from __future__ import annotations

from shared.schemas.kcmo_intake import FindingStatus, KcmoFinding, KcmoIntake, ProjectCategory, ScopeType


def check_kcmo_occupancy(intake: KcmoIntake) -> list[KcmoFinding]:
    findings: list[KcmoFinding] = []
    use_changed = bool(
        intake.existing_use
        and intake.proposed_use
        and intake.existing_use.strip().lower() != intake.proposed_use.strip().lower()
    )

    if intake.project_category in (ProjectCategory.MULTIFAMILY, ProjectCategory.COMMERCIAL) and intake.scope_type in (
        ScopeType.NEW_CONSTRUCTION,
        ScopeType.TENANT_FINISH,
        ScopeType.CHANGE_OF_USE,
    ):
        findings.append(
            KcmoFinding(
                status=FindingStatus.WARN,
                module="occupancy",
                finding="Certificate of Occupancy review likely required",
                explanation="New multifamily/commercial construction, tenant finish, or change of use typically requires CO closeout.",
                citation="IB139 / IB165",
                source_type="information_bulletin",
                next_action="Include CO request materials in the filing package.",
            )
        )

    if use_changed or intake.change_of_occupancy == "yes":
        findings.append(
            KcmoFinding(
                status=FindingStatus.WARN,
                module="occupancy",
                finding="Change of use/occupancy review likely required",
                explanation="Existing and proposed use differ, or change-of-occupancy was marked yes.",
                citation="IB139 / IB165",
                source_type="information_bulletin",
            )
        )
    elif intake.change_of_occupancy == "unknown":
        findings.append(
            KcmoFinding(
                status=FindingStatus.DATA_GAP,
                module="occupancy",
                finding="Change of occupancy status unknown",
                explanation="Confirm whether occupancy classification is changing.",
                citation="IB139 / IB165",
                required_user_data=["Change of occupancy yes/no"],
            )
        )

    if intake.project_category == ProjectCategory.COMMERCIAL and intake.public_access:
        findings.append(
            KcmoFinding(
                status=FindingStatus.WARN,
                module="occupancy",
                finding="Occupant load review may be required",
                explanation="Public/customer access areas often trigger occupant-load documentation.",
                citation="IB139 / Occupant Load Certificates",
                source_type="information_bulletin",
            )
        )

    if not findings:
        findings.append(
            KcmoFinding(
                status=FindingStatus.PASS,
                module="occupancy",
                finding="No occupancy-change triggers from intake",
                explanation="Update existing/proposed use or CO flags if occupancy closeout applies.",
                citation="IB139 / IB165",
            )
        )
    return findings
