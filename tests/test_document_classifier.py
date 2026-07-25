import pytest

from api.services import document_classifier


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("A201 Architectural Floor Plans.pdf", "architectural_plan"),
        ("Fire Sprinkler Package.pdf", "fire_protection_plan"),
        ("Electrical Lighting Plans.pdf", "electrical_plan"),
        ("Boundary Survey.pdf", "survey"),
        ("Owner Authorization.pdf", "supporting_document"),
    ],
)
def test_infer_document_type(filename: str, expected: str) -> None:
    assert document_classifier.infer_document_type(filename) == expected


@pytest.mark.asyncio
async def test_ai_classification_is_limited_to_known_types_and_project_permits(monkeypatch) -> None:
    async def fake_completion(*args, **kwargs):
        return """{
          "document_type": "mechanical_plan",
          "summary": "Mechanical schedules and HVAC layout.",
          "permit_types": ["mechanical", "not-a-project-permit"]
        }"""

    monkeypatch.setattr(document_classifier, "chat_completion", fake_completion)
    result = await document_classifier.classify_project_document(
        filename="M101.pdf",
        content=b"test document",
        content_type="application/pdf",
        permits=[{"permit_type": "mechanical", "permit_name": "Mechanical permit"}],
    )

    assert result == {
        "document_type": "mechanical_plan",
        "summary": "Mechanical schedules and HVAC layout.",
        "permit_types": ["mechanical"],
        "source": "ai",
    }
