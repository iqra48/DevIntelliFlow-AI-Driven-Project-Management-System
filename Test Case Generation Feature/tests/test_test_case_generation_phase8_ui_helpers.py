from ui.test_case_ui_helpers import (
    build_test_case_payload,
    extract_final_testable_requirements,
)


def item(requirement_id="REQ_1", requirement="Original text.", classification_type="FR"):
    return {
        "id": requirement_id,
        "requirement": requirement,
        "classification_type": classification_type,
    }


def test_extract_final_testable_requirements_keeps_fr():
    result = extract_final_testable_requirements([item(classification_type="FR")])

    assert result == [item(classification_type="FR")]


def test_extract_final_testable_requirements_keeps_nfr():
    result = extract_final_testable_requirements([item(classification_type="NFR")])

    assert result == [item(classification_type="NFR")]


def test_extract_final_testable_requirements_removes_mixed():
    result = extract_final_testable_requirements([item(classification_type="MIXED")])

    assert result == []


def test_extract_final_testable_requirements_removes_abstain():
    result = extract_final_testable_requirements([item(classification_type="ABSTAIN")])

    assert result == []


def test_extract_final_testable_requirements_removes_missing_id():
    raw = item()
    del raw["id"]

    result = extract_final_testable_requirements([raw])

    assert result == []


def test_extract_final_testable_requirements_removes_missing_requirement():
    raw = item()
    del raw["requirement"]

    result = extract_final_testable_requirements([raw])

    assert result == []


def test_extract_final_testable_requirements_removes_missing_classification_type():
    raw = item()
    del raw["classification_type"]

    result = extract_final_testable_requirements([raw])

    assert result == []


def test_extract_final_testable_requirements_preserves_requirement_text():
    text = "  Preserve this text exactly.  "

    result = extract_final_testable_requirements([item(requirement=text)])

    assert result[0]["requirement"] == text


def test_extract_final_testable_requirements_does_not_inspect_text_content():
    result = extract_final_testable_requirements(
        [item(requirement="Any arbitrary product sentence.")]
    )

    assert len(result) == 1


def test_selected_payload_shape_matches_backend_expectation():
    requirements = [item()]

    payload = build_test_case_payload(requirements, "Context", "mvp_fast")

    assert payload == {
        "requirements": requirements,
        "project_context": "Context",
        "mode": "mvp_fast",
    }
