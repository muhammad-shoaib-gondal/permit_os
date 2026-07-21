from api.models import ProjectFile, ProjectPermit
from api.services.project_service import _permit_has_review_document


def project_file(file_type: str, name: str = "document.pdf") -> ProjectFile:
    return ProjectFile(
        file_id="file-1",
        project_id="project-1",
        name=name,
        file_type=file_type,
        size=100,
        storage_path=name,
    )


def permit(required_documents: list[str]) -> ProjectPermit:
    return ProjectPermit(
        permit_id="permit-1",
        project_id="project-1",
        permit_type="electrical",
        permit_name="Electrical permit",
        required_documents=required_documents,
    )


def test_one_matching_required_document_unlocks_review() -> None:
    files = [project_file("electrical_plan", "E101 Electrical Plans.pdf")]
    item = permit(["Electrical plans", "Electrical contractor license"])

    assert _permit_has_review_document(item, files) is True


def test_unrelated_document_does_not_unlock_review() -> None:
    files = [project_file("survey", "Boundary Survey.pdf")]
    item = permit(["Electrical plans", "Electrical contractor license"])

    assert _permit_has_review_document(item, files) is False


def test_architectural_plan_matches_generic_construction_plans() -> None:
    files = [project_file("architectural_plan", "A100 Plan Set.pdf")]
    item = permit(["construction plans when formal review applies"])

    assert _permit_has_review_document(item, files) is True
