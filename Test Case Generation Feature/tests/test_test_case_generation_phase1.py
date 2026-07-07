import pytest

from app.services.test_case_generation.models import RequirementForTestCase
from app.services.test_case_generation.validation import (
    TestCaseValidationError,
    chunk_requirements,
    normalize_requirement,
    normalize_requirements,
)


def raw_requirement(
    requirement_id="REQ_1",
    requirement="The system shall export reports.",
    classification_type="FR",
):
    return {
        "id": requirement_id,
        "requirement": requirement,
        "classification_type": classification_type,
    }


def test_valid_fr_requirement_is_accepted():
    result = normalize_requirement(raw_requirement(classification_type="FR"))

    assert result == RequirementForTestCase(
        id="REQ_1",
        requirement="The system shall export reports.",
        classification_type="FR",
    )


def test_valid_nfr_requirement_is_accepted():
    result = normalize_requirement(
        raw_requirement(
            requirement="The system shall remain available during maintenance.",
            classification_type="NFR",
        )
    )

    assert result.classification_type == "NFR"


@pytest.mark.parametrize("classification_type", ["MIXED", "ABSTAIN"])
def test_non_final_classification_types_are_rejected(classification_type):
    with pytest.raises(TestCaseValidationError):
        normalize_requirement(raw_requirement(classification_type=classification_type))


def test_mixed_requirement_is_rejected():
    with pytest.raises(TestCaseValidationError):
        normalize_requirement(raw_requirement(classification_type="MIXED"))


def test_abstain_requirement_is_rejected():
    with pytest.raises(TestCaseValidationError):
        normalize_requirement(raw_requirement(classification_type="ABSTAIN"))


def test_missing_id_is_rejected():
    raw = raw_requirement()
    del raw["id"]

    with pytest.raises(TestCaseValidationError):
        normalize_requirement(raw)


def test_empty_id_is_rejected():
    with pytest.raises(TestCaseValidationError):
        normalize_requirement(raw_requirement(requirement_id=" "))


def test_missing_requirement_text_is_rejected():
    raw = raw_requirement()
    del raw["requirement"]

    with pytest.raises(TestCaseValidationError):
        normalize_requirement(raw)


def test_empty_requirement_text_is_rejected():
    with pytest.raises(TestCaseValidationError):
        normalize_requirement(raw_requirement(requirement=" "))


def test_missing_classification_type_is_rejected():
    raw = raw_requirement()
    del raw["classification_type"]

    with pytest.raises(TestCaseValidationError):
        normalize_requirement(raw)


def test_unknown_classification_type_is_rejected():
    with pytest.raises(TestCaseValidationError):
        normalize_requirement(raw_requirement(classification_type="OTHER"))


def test_duplicate_ids_are_rejected():
    raw_requirements = [
        raw_requirement(requirement_id="REQ_1"),
        raw_requirement(requirement_id="REQ_1", classification_type="NFR"),
    ]

    with pytest.raises(TestCaseValidationError):
        normalize_requirements(raw_requirements)


def test_too_many_requirements_for_mvp_fast_are_rejected():
    raw_requirements = [
        raw_requirement(requirement_id=f"REQ_{index}")
        for index in range(1, 5)
    ]

    with pytest.raises(TestCaseValidationError):
        normalize_requirements(raw_requirements, mode="mvp_fast")


def test_too_many_requirements_for_balanced_are_rejected():
    raw_requirements = [
        raw_requirement(requirement_id=f"REQ_{index}")
        for index in range(1, 5)
    ]

    with pytest.raises(TestCaseValidationError):
        normalize_requirements(raw_requirements, mode="balanced")


def test_chunking_works_for_mvp_fast():
    requirements = [
        RequirementForTestCase(f"REQ_{index}", "The system shall export reports.", "FR")
        for index in range(1, 7)
    ]

    chunks = chunk_requirements(requirements, mode="mvp_fast")

    assert [len(chunk) for chunk in chunks] == [3, 3]


def test_chunking_works_for_balanced():
    requirements = [
        RequirementForTestCase(f"REQ_{index}", "The system shall export reports.", "FR")
        for index in range(1, 5)
    ]

    chunks = chunk_requirements(requirements, mode="balanced")

    assert [len(chunk) for chunk in chunks] == [3, 1]


def test_invalid_mode_is_rejected():
    with pytest.raises(TestCaseValidationError):
        normalize_requirements([raw_requirement()], mode="slow")
