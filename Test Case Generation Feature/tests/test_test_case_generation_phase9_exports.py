from pathlib import Path

from ui.test_case_ui_helpers import (
    build_test_case_json_download,
    flatten_test_case_result_for_csv,
)


def sample_test_case(case_id="TC_REQ_1_001"):
    return {
        "test_case_id": case_id,
        "requirement_id": "REQ_1",
        "title": "Verify record export",
        "objective": "Confirm the requirement is satisfied.",
        "test_type": "Positive",
        "technique_used": "Functional verification",
        "priority": "High",
        "preconditions": ["System is available", "User has access"],
        "test_data": {"record_id": "R-1"},
        "steps": [
            {
                "step_number": 1,
                "action": "Perform export",
                "expected_result": "Export completes",
            },
            {
                "step_number": 2,
                "action": "Review output",
                "expected_result": "Output is available",
            },
        ],
        "expected_result": "The record is exported.",
        "assumption_required": False,
        "assumptions": ["Standard configuration"],
        "traceability": {
            "requirement_id": "REQ_1",
            "coverage_item": "Verify stated behavior.",
            "technique_used": "Functional verification",
        },
    }


def sample_result(test_cases=None):
    return {
        "status": "SUCCESS",
        "results": [
            {
                "requirement_id": "REQ_1",
                "requirement_text": "The system shall export records.",
                "requirement_type": "FR",
                "status": "SUCCESS",
                "test_cases": test_cases
                if test_cases is not None
                else [sample_test_case()],
                "missing_information": ["Missing browser matrix"],
                "assumptions": ["Default deployment"],
                "warnings": ["Review environment"],
                "reason": None,
            }
        ],
        "plans": [],
        "warnings": [],
        "budget": {},
    }


def test_flatten_returns_empty_for_non_dict_input():
    assert flatten_test_case_result_for_csv(None) == []


def test_flatten_returns_one_row_for_one_bundle_with_one_test_case():
    rows = flatten_test_case_result_for_csv(sample_result())

    assert len(rows) == 1


def test_flatten_returns_multiple_rows_for_multiple_test_cases():
    rows = flatten_test_case_result_for_csv(
        sample_result([sample_test_case("TC_REQ_1_001"), sample_test_case("TC_REQ_1_002")])
    )

    assert len(rows) == 2


def test_flatten_includes_blocked_requirement_row_when_no_test_cases_exist():
    result = sample_result([])
    result["results"][0]["status"] = "BLOCKED_MISSING_INFORMATION"

    rows = flatten_test_case_result_for_csv(result)

    assert len(rows) == 1
    assert rows[0]["test_case_id"] == ""


def test_csv_row_contains_requirement_id():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["requirement_id"] == "REQ_1"


def test_csv_row_contains_requirement_text():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["requirement_text"] == "The system shall export records."


def test_csv_row_contains_requirement_type():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["requirement_type"] == "FR"


def test_csv_row_contains_bundle_status():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["bundle_status"] == "SUCCESS"


def test_csv_row_contains_test_case_id():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["test_case_id"] == "TC_REQ_1_001"


def test_csv_row_contains_title_objective_test_type_priority():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["title"] == "Verify record export"
    assert row["objective"] == "Confirm the requirement is satisfied."
    assert row["test_type"] == "Positive"
    assert row["priority"] == "High"


def test_csv_row_formats_preconditions_list_with_separator():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["preconditions"] == "System is available | User has access"


def test_csv_row_serializes_test_data_dict_as_json_string():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["test_data"] == '{"record_id": "R-1"}'


def test_csv_row_formats_steps_as_readable_string():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["steps"] == (
        "1. Perform export => Export completes | "
        "2. Review output => Output is available"
    )


def test_csv_row_includes_final_expected_result():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["expected_result"] == "The record is exported."


def test_csv_row_includes_assumptions():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["test_case_assumptions"] == "Standard configuration"


def test_csv_row_includes_traceability_coverage_item():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["traceability_coverage_item"] == "Verify stated behavior."


def test_missing_optional_fields_do_not_crash_and_produce_empty_strings():
    result = sample_result([{}])

    row = flatten_test_case_result_for_csv(result)[0]

    assert row["test_case_id"] == ""
    assert row["traceability_coverage_item"] == ""


def test_build_test_case_json_download_returns_pretty_json_string():
    text = build_test_case_json_download({"status": "SUCCESS"})

    assert text == '{\n  "status": "SUCCESS"\n}'


def test_build_test_case_json_download_returns_empty_object_for_invalid_input():
    assert build_test_case_json_download(None) == "{}"


def test_no_text_content_inspection_exists_in_helper_module():
    text = Path("ui/test_case_ui_helpers.py").read_text()

    assert ".lower(" not in text

