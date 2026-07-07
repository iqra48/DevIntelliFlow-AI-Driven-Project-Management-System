import re
from pathlib import Path

from app.services.test_case_generation.prompts import (
    TEST_CASE_PROMPT_VERSION,
    build_planner_system_prompt,
)
from ui.test_case_ui_helpers import (
    EMPTY_TEST_DATA_TEXT,
    build_test_case_json_download,
    flatten_test_case_result_for_csv,
    professional_csv_field_order,
    provider_metadata_display_rows,
    selected_count_message,
    selection_limit_message,
    status_display_message,
)


def sample_result() -> dict:
    return {
        "status": "SUCCESS",
        "results": [
            {
                "requirement_id": "REQ_1",
                "requirement_text": "The system shall export records.",
                "requirement_type": "FR",
                "status": "SUCCESS",
                "missing_information": ["Target file format"],
                "assumptions": ["Default configuration"],
                "warnings": ["Review before execution"],
                "reason": "",
                "test_cases": [
                    {
                        "test_case_id": "TC_REQ_1_001",
                        "requirement_id": "REQ_1",
                        "title": "Export records",
                        "objective": "Verify the stated export behavior.",
                        "test_type": "Positive",
                        "priority": "High",
                        "preconditions": ["System is available"],
                        "steps": [
                            {
                                "step_number": 1,
                                "action": "Exercise the export capability",
                                "expected_result": "Export output is produced",
                            }
                        ],
                        "test_data": {"record": "valid"},
                        "expected_result": "Records are exported.",
                        "assumptions": ["Configured prerequisite exists"],
                        "traceability": {
                            "requirement_id": "REQ_1",
                            "coverage_item": "Export records",
                            "technique_used": "Functional verification",
                            "source_basis": ["shall export records"],
                        },
                    }
                ],
            }
        ],
        "budget": {},
    }


def test_success_maps_to_draft_safe_wording():
    message = status_display_message("SUCCESS")

    assert message == "Generated draft passed automated checks"
    assert "APP" + "ROVED" not in message


def test_needs_review_maps_to_human_review_wording():
    assert status_display_message("NEEDS_REVIEW") == "Human review recommended"


def test_blocked_maps_to_clarification_wording():
    assert status_display_message("BLOCKED_MISSING_INFORMATION") == "Clarification needed"


def test_csv_flatten_includes_professional_fields():
    row = flatten_test_case_result_for_csv(sample_result())[0]

    assert row["Test Case ID"] == "TC_REQ_1_001"
    assert row["Requirement Covered"] == "REQ_1"
    assert row["Title"] == "Export records"
    assert row["Type"] == "Positive"
    assert row["Priority"] == "High"
    assert row["Preconditions"] == "System is available"
    assert row["Expected Result"] == "Records are exported."
    assert row["Missing Information"] == "Target file format"
    assert row["Status"] == "SUCCESS"
    assert row["Warnings"] == "Review before execution"


def test_professional_csv_order_starts_with_display_fields():
    rows = flatten_test_case_result_for_csv(sample_result())

    assert professional_csv_field_order(rows)[:5] == [
        "Test Case ID",
        "Requirement Covered",
        "Title",
        "Type",
        "Priority",
    ]


def test_user_facing_csv_excludes_traceability_and_source_basis_columns():
    rows = flatten_test_case_result_for_csv(sample_result())

    fields = professional_csv_field_order(rows)

    assert "Traceability Requirement ID" not in fields
    assert "Traceability Coverage Item" not in fields
    assert "Traceability Technique" not in fields
    assert "Source Basis" not in fields


def test_json_export_remains_raw_backend_response():
    text = build_test_case_json_download(sample_result())

    assert '"traceability"' in text
    assert '"source_basis"' in text


def test_test_data_is_present_in_user_facing_csv_field_list():
    assert "Test Data" in professional_csv_field_order(flatten_test_case_result_for_csv(sample_result()))


def test_empty_test_data_gets_user_friendly_text_without_fake_values():
    result = sample_result()
    result["results"][0]["test_cases"][0]["test_data"] = {}

    row = flatten_test_case_result_for_csv(result)[0]

    assert row["Test Data"] == EMPTY_TEST_DATA_TEXT
    assert "fake" not in row["Test Data"].casefold()
    assert "example" not in row["Test Data"].casefold()
    assert "john" not in row["Test Data"].casefold()
    assert "password" not in row["Test Data"].casefold()


def test_main_streamlit_template_excludes_traceability_and_source_basis():
    text = Path("ui/streamlit_app.py").read_text(encoding="utf-8")
    start = text.index('"Test Case ID"')
    end = text.index('if st.button("Generate Requirements"')
    template_text = text[start:end]

    assert "Traceability" not in template_text
    assert "Source Basis" not in template_text


def test_selection_messages_are_user_friendly():
    assert selection_limit_message(5) == (
        "Select up to 5 requirements for test case generation."
    )
    assert selected_count_message(2, 5) == "Selected: 2 / 5"


def test_streamlit_has_one_test_case_generation_action_and_no_estimate_button():
    text = Path("ui/streamlit_app.py").read_text(encoding="utf-8")

    actions = re.findall(r'st\.button\(\s*"Generate Test Cases"', text)

    assert len(actions) == 1
    assert "Estimate Test Case Budget" not in text
    assert 'TEST_CASE_MODE = "mvp_fast"' in text


def test_streamlit_uses_phase15f_user_facing_labels():
    text = Path("ui/streamlit_app.py").read_text(encoding="utf-8")

    assert 'st.title("AI Test Case Generator")' in text
    assert 'st.subheader("Select Requirements")' in text
    assert '"Project context (optional)"' in text
    assert 'st.subheader("Generated Test Cases")' in text
    assert 'st.markdown("#### Download Test Cases")' in text


def test_phase15f_r_replaces_large_warning_with_subtle_review_caption():
    text = Path("ui/streamlit_app.py").read_text(encoding="utf-8")

    assert "Generated test cases are AI-assisted QA drafts" not in text
    assert "Review generated test cases before execution." in text


def test_technical_details_are_opt_in_and_absent_from_normal_result_renderer():
    text = Path("ui/streamlit_app.py").read_text(encoding="utf-8")
    result_start = text.index("def render_test_case_result")
    result_end = text.index('if st.button("Generate Requirements"')
    normal_result = text[result_start:result_end]

    assert '"Show technical details"' in normal_result
    assert "value=False" in normal_result
    assert "if show_technical_details:" in normal_result
    assert "render_technical_details(result)" in normal_result
    assert "Provider Metadata" not in normal_result
    assert "Planner coverage" not in normal_result


def test_download_buttons_and_project_context_guidance_remain_visible():
    text = Path("ui/streamlit_app.py").read_text(encoding="utf-8")

    assert '"Download as JSON"' in text
    assert '"Download as CSV"' in text
    assert (
        "Add project context to help generate more positive, negative, and "
        '"\n            "boundary scenarios when supported."'
    ) in text


def test_planner_v13_contains_source_supported_balanced_coverage_target():
    prompt = build_planner_system_prompt().casefold()

    assert TEST_CASE_PROMPT_VERSION == "planner_v13"
    assert "balanced coverage target" in prompt
    assert "negative coverage item only when" in prompt
    assert "boundary coverage item only when" in prompt
    assert "never invent unsupported negative or boundary coverage" in prompt
    assert "prefer one to three useful coverage items" in prompt


def test_phase15f_python_does_not_add_domain_keyword_branching():
    text = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in ["ui/streamlit_app.py", "ui/test_case_ui_helpers.py"]
    )
    domain_branch = re.compile(
        r"\bif\s+[\"'](?:login|upload|report|password|dashboard)[\"']",
        re.IGNORECASE,
    )

    assert domain_branch.search(text) is None


def test_provider_metadata_still_available_for_diagnostics():
    rows = provider_metadata_display_rows(
        {
            "primary_provider": "groq",
            "provider_role_map": {
                "planner": "cerebras",
                "generator": "groq",
                "reviewer": "cerebras",
            },
            "fallback_used": False,
        }
    )

    labels = {row["label"] for row in rows}
    assert "Provider strategy" in labels
    assert "Fallback used" in labels


def test_ui_helpers_and_streamlit_do_not_display_approved_wording():
    text = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in ["ui/test_case_ui_helpers.py", "ui/streamlit_app.py"]
    )

    assert "APP" + "ROVED" not in text
    assert "Approved" not in text


def test_backend_intelligence_files_do_not_contain_phase15b_r2_ui_text():
    forbidden_ui_text = "No safe test cases were generated for this requirement."
    for path in [
        "app/services/test_case_generation/prompts.py",
        "app/services/test_case_generation/planner.py",
        "app/services/test_case_generation/generator.py",
        "app/services/test_case_generation/reviewer.py",
        "app/services/test_case_generation/orchestrator.py",
    ]:
        assert forbidden_ui_text not in Path(path).read_text(encoding="utf-8")
