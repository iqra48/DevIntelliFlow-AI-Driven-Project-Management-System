# ui_temp.py
import hashlib
import streamlit as st
import requests
import pandas as pd
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure the local ui package is importable when running via streamlit
ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ui.test_case_ui_helpers import (
    build_test_case_json_download,
    build_test_case_payload,
    assumptions_display_text,
    EMPTY_PRECONDITIONS_TEXT,
    EMPTY_TEST_DATA_TEXT,
    extract_final_testable_requirements,
    flatten_test_case_result_for_csv,
    professional_csv_field_order,
    provider_metadata_display_rows,
    selected_count_message,
    selection_limit_message,
    bundle_status_display_message,
    is_internal_planner_issue,
    status_display_message,
    status_notice_kind,
)

if "user_input" not in st.session_state:
    st.session_state.user_input = ""

if "results" not in st.session_state:
    st.session_state.results = []

if "df_results" not in st.session_state:
    st.session_state.df_results = None

if "cache" not in st.session_state:
    st.session_state.cache = {}

if "generated_requirements" not in st.session_state:
    st.session_state.generated_requirements = []

if "selected_test_requirements" not in st.session_state:
    st.session_state.selected_test_requirements = []

if "test_case_estimate" not in st.session_state:
    st.session_state.test_case_estimate = None

if "test_case_result" not in st.session_state:
    st.session_state.test_case_result = None

if "test_case_error" not in st.session_state:
    st.session_state.test_case_error = None

if "test_case_estimate_signature" not in st.session_state:
    st.session_state.test_case_estimate_signature = None

if "test_case_max_requirements" not in st.session_state:
    st.session_state.test_case_max_requirements = 3

API_BASE = os.getenv("REQ_API_BASE", "http://localhost:8000")
API_TEXT_ENDPOINT = f"{API_BASE.rstrip('/')}/process"
API_FILE_ENDPOINT = f"{API_BASE.rstrip('/')}/process_file"
API_TEST_CASE_ESTIMATE_ENDPOINT = f"{API_BASE.rstrip('/')}/generate_test_cases/estimate"
API_TEST_CASE_ENDPOINT = f"{API_BASE.rstrip('/')}/generate_test_cases"
REQUEST_TIMEOUT = int(os.getenv("REQ_UI_TIMEOUT", "1200"))
TEST_CASE_ESTIMATE_TIMEOUT = int(os.getenv("REQ_UI_TEST_CASE_ESTIMATE_TIMEOUT", "120"))
TEST_CASE_GENERATION_TIMEOUT = int(os.getenv("REQ_UI_TEST_CASE_TIMEOUT", "1200"))
TEST_CASE_MODE = "mvp_fast"
DEFAULT_MAX_REQUIREMENTS = 3

st.set_page_config(page_title="AI Test Case Generator", layout="wide")
st.title("AI Test Case Generator")


st.subheader("Input Source")
input_option = st.radio("Choose input type:", ["Write Text", "Upload File"])
user_input = ""

if input_option == "Write Text":
    st.session_state.user_input = st.text_area(
        "Enter your requirement, user story, or paragraph:",
        st.session_state.user_input
    )
    user_input = st.session_state.user_input

else:
    uploaded_file = st.file_uploader(
        "Upload PDF, DOCX, TXT, CSV, XLSX",
        type=["pdf", "docx", "txt", "csv", "xlsx"]
    )
    if uploaded_file:
        st.success(f"Uploaded: {uploaded_file.name}")
    user_input = ""

def get_cache_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def call_backend_text(text: str, timeout: int = REQUEST_TIMEOUT) -> Optional[dict]:
    try:
        payload = {"text": text}
        resp = requests.post(API_TEXT_ENDPOINT, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Backend error: {e}")
        return None



def call_backend_file(file, timeout: int = REQUEST_TIMEOUT) -> Optional[dict]:
    try:
        files = {"file": (file.name, file.getvalue())}
        resp = requests.post(API_FILE_ENDPOINT, files=files, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Backend error: {e}")
        return None


def reset_test_case_state() -> None:
    st.session_state.selected_test_requirements = []
    st.session_state.test_case_estimate = None
    st.session_state.test_case_result = None
    st.session_state.test_case_error = None
    st.session_state.test_case_estimate_signature = None
    st.session_state.test_case_max_requirements = DEFAULT_MAX_REQUIREMENTS


def call_test_case_estimate(
    requirements: list[dict],
    project_context: str,
    mode: str,
) -> dict:
    payload = build_test_case_payload(requirements, project_context, mode)
    resp = requests.post(
        API_TEST_CASE_ESTIMATE_ENDPOINT,
        json=payload,
        timeout=TEST_CASE_ESTIMATE_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def call_generate_test_cases(
    requirements: list[dict],
    project_context: str,
    mode: str,
) -> dict:
    payload = build_test_case_payload(requirements, project_context, mode)
    resp = requests.post(
        API_TEST_CASE_ENDPOINT,
        json=payload,
        timeout=TEST_CASE_GENERATION_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def render_list(label: str, values: list) -> None:
    if values:
        st.markdown(f"**{label}:**")
        for value in values:
            st.write(f"- {value}")


def render_text_field(label: str, value) -> None:
    text = str(value).strip() if value is not None else ""
    st.markdown(f"**{label}:** {text or '-'}")


def render_mapping_table(label: str, value) -> None:
    if isinstance(value, dict) and value:
        st.markdown(f"**{label}:**")
        rows = [{"Field": key, "Value": value[key]} for key in value]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        render_text_field(label, EMPTY_TEST_DATA_TEXT)


def render_preconditions(values) -> None:
    if isinstance(values, list) and values:
        render_list("Preconditions", values)
    else:
        render_text_field("Preconditions", EMPTY_PRECONDITIONS_TEXT)


def render_assumptions(values) -> None:
    if isinstance(values, list) and values:
        render_list("Assumptions", values)
    else:
        render_text_field("Assumptions", assumptions_display_text(values))


def render_status_notice(prefix: str, status: str, reason: str | None = None) -> None:
    message = bundle_status_display_message(status, reason)
    notice_kind = status_notice_kind(status)
    text = f"{prefix}: {message}"
    if status == "BLOCKED_MISSING_INFORMATION" and not is_internal_planner_issue(reason):
        text = f"{text}. Clarification is needed before generation can continue."
    if notice_kind == "success":
        st.success(text)
    elif notice_kind == "info":
        st.info(text)
    elif notice_kind == "warning":
        st.warning(text)
    else:
        st.error(text)


def render_technical_details(result: dict) -> None:
    budget = result.get("budget") or {}
    plans = result.get("plans") or []
    warnings = result.get("warnings") or []

    if budget:
        st.markdown("#### Provider Metadata")
        budget_cols = st.columns(4)
        budget_cols[0].metric("Mode", budget.get("mode", "-"))
        budget_cols[1].metric("Estimated calls", budget.get("estimated_calls", 0))
        budget_cols[2].metric("Estimated tokens", budget.get("estimated_tokens", 0))
        budget_cols[3].metric("Calls used", budget.get("calls_used", 0))
        provider_rows = provider_metadata_display_rows(budget)
        if provider_rows:
            st.dataframe(
                pd.DataFrame(provider_rows),
                hide_index=True,
                use_container_width=True,
            )

    if plans:
        st.markdown("#### Planner coverage")
        for plan in plans:
            st.markdown(
                f"**{plan.get('requirement_id', '-')}: "
                f"{plan.get('requirement_type', '-')}**"
            )
            coverage_items = plan.get("coverage_items") or []
            if coverage_items:
                st.dataframe(
                    pd.DataFrame(coverage_items),
                    hide_index=True,
                    use_container_width=True,
                )

    render_list("Warnings", warnings)

    if budget.get("rate_limit_stage") or budget.get("rate_limit_type"):
        st.error(
            "Rate-limit signal: "
            f"stage={budget.get('rate_limit_stage') or '-'}, "
            f"type={budget.get('rate_limit_type') or '-'}"
        )
    if result.get("status") == "PROVIDER_FAILED":
        st.error("Provider error occurred during test-case generation.")


def render_test_case_result(result: dict) -> None:
    st.subheader("Generated Test Cases")
    st.caption("Generated source-grounded test scenarios")
    show_technical_details = st.checkbox(
        "Show technical details",
        value=False,
        key="show_test_case_technical_details",
    )
    if show_technical_details:
        render_technical_details(result)

    for bundle in result.get("results") or []:
        st.markdown("---")
        st.markdown("### Requirement")
        render_text_field("Requirement ID", bundle.get("requirement_id", "-"))
        render_text_field("Requirement text", bundle.get("requirement_text", ""))
        bundle_status = bundle.get("status", "UNKNOWN")
        render_status_notice("Status", bundle_status, bundle.get("reason"))
        test_cases = bundle.get("test_cases") or []
        st.write(f"Test case count: **{len(test_cases)}**")

        if not test_cases:
            st.info(
                "No safe test cases were generated for this requirement."
            )
            render_list("Missing information", bundle.get("missing_information") or [])
            if bundle.get("reason"):
                st.write(f"Reason: {bundle['reason']}")
            continue

        for test_case in test_cases:
            title = (
                f"{test_case.get('test_case_id', '-')}: "
                f"{test_case.get('title', 'Untitled test case')}"
            )
            with st.expander(title, expanded=False):
                render_text_field(
                    "Test Case ID",
                    test_case.get("test_case_id", "-"),
                )
                render_text_field(
                    "Requirement Covered",
                    test_case.get("requirement_id")
                    or bundle.get("requirement_id", "-"),
                )
                render_text_field("Title", test_case.get("title", ""))
                render_text_field("Type", test_case.get("test_type", "-"))
                render_text_field("Priority", test_case.get("priority", "-"))
                render_preconditions(test_case.get("preconditions") or [])

                steps = test_case.get("steps") or []
                if steps:
                    step_rows = [
                        {
                            "Step #": step.get("step_number"),
                            "Action": step.get("action"),
                            "Expected Result": step.get("expected_result"),
                        }
                        for step in steps
                    ]
                    st.markdown("**Steps:**")
                    st.dataframe(
                        pd.DataFrame(step_rows),
                        hide_index=True,
                        use_container_width=True,
                    )
                else:
                    render_text_field("Steps", "-")

                render_mapping_table("Test Data", test_case.get("test_data") or {})
                render_text_field(
                    "Expected Result",
                    test_case.get("expected_result", ""),
                )
                render_assumptions(test_case.get("assumptions") or [])


if st.button("Generate Requirements", type="primary"):
    if input_option == "Write Text" and (not user_input or not user_input.strip()):
        st.warning("Please provide input first.")
    elif input_option != "Write Text" and not uploaded_file:
        st.warning("Please upload a file first.")
    else:
        with st.spinner("Generating and classifying requirements..."):
            if input_option == "Write Text":
                cache_key = get_cache_key(user_input)
                if cache_key in st.session_state.cache:
                    data = st.session_state.cache[cache_key]
                else:
                    data = call_backend_text(user_input)
                    st.session_state.cache[cache_key] = data
            else:
                data = call_backend_file(uploaded_file)

        if not data:
            st.error(
                "No response from backend. Ensure the API is running and reachable at: "
                + (API_TEXT_ENDPOINT if input_option == "Write Text" else API_FILE_ENDPOINT)
            )
        else:
            st.session_state.results = data.get("results", []) or []
            st.session_state.generated_requirements = st.session_state.results
            reset_test_case_state()
            results = st.session_state.results

            if not results:
                st.warning("Backend returned no requirements.")
            else:
                rows = []
                seen_texts = set()
                for i, item in enumerate(results):
                    req_id = item.get("id") or f"REQ_{i+1}"
                    imp = (
                        item.get("requirement") or
                        item.get("rewritten") or
                        item.get("original_generated") or
                        item.get("original_requirement") or
                        ""
                    )
                    imp = (imp or "").strip()

                    classification = item.get("classification", {})
                    c_status = classification.get("status")
                    if c_status == "SUCCESS":
                        label = item.get("classification_type") or classification.get("type") or "UNKNOWN"
                    elif c_status == "ABSTAIN" or item.get("classification_type") == "ABSTAIN":
                        label = "ABSTAIN"
                    else:
                        label = "UNKNOWN"

                    norm = " ".join(imp.split()).lower()
                    if not norm or norm in seen_texts:
                        continue
                    seen_texts.add(norm)

                    rows.append({
                        "id": req_id,
                        "requirement": imp,
                        "label": label,
                    })

                df = pd.DataFrame(rows)
                df = df[["id", "requirement", "label"]]

                st.session_state.df_results = df

                st.success("Requirements generated and classified.")

if st.session_state.df_results is not None and not st.session_state.df_results.empty:
    st.markdown("---")
    st.subheader("Select Requirements")

    final_requirements = extract_final_testable_requirements(
        st.session_state.generated_requirements
    )

    if not final_requirements:
        st.info(
            "No final FR/NFR requirements are available for test case generation."
        )
    else:
        mode = TEST_CASE_MODE
        max_requirements = st.session_state.test_case_max_requirements
        st.info(selection_limit_message(max_requirements))

        selection_rows = [
            {
                "Select": any(
                    selected.get("id") == requirement["id"]
                    for selected in st.session_state.selected_test_requirements
                ),
                "ID": requirement["id"],
                "Type": requirement["classification_type"],
                "Requirement": requirement["requirement"],
            }
            for requirement in final_requirements
        ]
        selection_df = pd.DataFrame(selection_rows)

        edited_selection = st.data_editor(
            selection_df,
            use_container_width=True,
            hide_index=True,
            disabled=["ID", "Type", "Requirement"],
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "Select",
                    help="Choose final FR/NFR requirements for test case generation.",
                    default=False,
                )
            },
            key="test_case_requirement_selector",
        )

        selected_ids = set(
            edited_selection.loc[edited_selection["Select"], "ID"].tolist()
        )
        selected_requirements = [
            requirement
            for requirement in final_requirements
            if requirement["id"] in selected_ids
        ]
        st.session_state.selected_test_requirements = selected_requirements
        selected_count = len(selected_requirements)
        st.caption(selected_count_message(selected_count, max_requirements))

        project_context = st.text_area(
            "Project context (optional)",
            placeholder=(
                "Example: Web-based inventory system for internal business users."
            ),
            key="test_case_project_context",
        )
        st.caption(
            "Add project context to help generate more positive, negative, and "
            "boundary scenarios when supported."
        )

        current_estimate_signature = (
            tuple(sorted(selected_ids)),
            project_context,
            mode,
        )

        if st.session_state.test_case_estimate_signature != current_estimate_signature:
            st.session_state.test_case_estimate = None
            st.session_state.test_case_result = None
            st.session_state.test_case_error = None

        if selected_count == 0:
            st.session_state.test_case_estimate_signature = current_estimate_signature
        elif selected_count > max_requirements:
            st.warning(selection_limit_message(max_requirements))
            st.session_state.test_case_estimate_signature = current_estimate_signature
        elif st.session_state.test_case_estimate is None:
            try:
                st.session_state.test_case_estimate = call_test_case_estimate(
                    selected_requirements,
                    project_context,
                    mode,
                )
                st.session_state.test_case_estimate_signature = current_estimate_signature
                estimated_max = st.session_state.test_case_estimate.get(
                    "max_requirements"
                )
                if isinstance(estimated_max, int) and estimated_max > 0:
                    st.session_state.test_case_max_requirements = estimated_max
                    max_requirements = estimated_max
            except Exception as e:
                st.session_state.test_case_error = str(e)
                st.session_state.test_case_estimate_signature = current_estimate_signature

        estimate = st.session_state.test_case_estimate
        can_generate = (
            selected_count > 0
            and selected_count <= max_requirements
            and bool(estimate)
            and estimate.get("allowed") is True
            and st.session_state.test_case_estimate_signature
            == current_estimate_signature
        )

        if st.button(
            "Generate Test Cases",
            type="primary",
            disabled=not can_generate,
        ):
            st.session_state.test_case_error = None
            try:
                with st.spinner("Generating source-grounded test scenarios..."):
                    st.session_state.test_case_result = call_generate_test_cases(
                        selected_requirements,
                        project_context,
                        mode,
                    )
            except Exception as e:
                st.session_state.test_case_error = str(e)
                st.error(f"Test case generation failed: {e}")

        if estimate and estimate.get("allowed") is False:
            st.warning(
                "The selected requirements cannot be generated safely. "
                "Adjust the selection or project context."
            )

        if st.session_state.test_case_error:
            st.error(st.session_state.test_case_error)

        if st.session_state.test_case_result:
            render_test_case_result(st.session_state.test_case_result)
            st.markdown("#### Download Test Cases")
            st.caption("Review generated test cases before execution.")
            st.download_button(
                "Download as JSON",
                build_test_case_json_download(
                    st.session_state.test_case_result
                ).encode("utf-8"),
                file_name="generated_test_cases.json",
                mime="application/json",
            )

            test_case_rows = flatten_test_case_result_for_csv(
                st.session_state.test_case_result
            )
            if test_case_rows:
                test_case_df = pd.DataFrame(test_case_rows)
                test_case_df = test_case_df[
                    professional_csv_field_order(test_case_rows)
                ]
                st.download_button(
                    "Download as CSV",
                    test_case_df.to_csv(index=False).encode("utf-8"),
                    file_name="generated_test_cases.csv",
                    mime="text/csv",
                )
            else:
                st.info("No test case rows available for CSV export.")
