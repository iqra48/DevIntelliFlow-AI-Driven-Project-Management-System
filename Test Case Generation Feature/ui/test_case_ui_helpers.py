import json


ALLOWED_TEST_REQUIREMENT_TYPES = {"FR", "NFR"}
PUBLIC_TEST_CASE_STATUSES = {
    "SUCCESS",
    "NEEDS_REVIEW",
    "BLOCKED_MISSING_INFORMATION",
    "FAILED_SCHEMA_VALIDATION",
    "RATE_LIMITED",
    "PROVIDER_FAILED",
}
STATUS_DISPLAY_MESSAGES = {
    "SUCCESS": "Generated draft passed automated checks",
    "NEEDS_REVIEW": "Human review recommended",
    "BLOCKED_MISSING_INFORMATION": "Clarification needed",
    "FAILED_SCHEMA_VALIDATION": "Generated draft failed schema checks",
    "RATE_LIMITED": "Provider rate limit interrupted generation",
    "PROVIDER_FAILED": "Provider error interrupted generation",
}

USER_FACING_TEST_CASE_FIELDS = [
    "Test Case ID",
    "Requirement Covered",
    "Title",
    "Type",
    "Priority",
    "Preconditions",
    "Steps",
    "Test Data",
    "Expected Result",
    "Assumptions",
    "Missing Information",
    "Status",
    "Warnings",
]
PROFESSIONAL_CSV_FIELDS = USER_FACING_TEST_CASE_FIELDS
EMPTY_TEST_DATA_TEXT = (
    "No specific test data was provided by the requirement. Use valid data "
    "according to configured system rules."
)
EMPTY_PRECONDITIONS_TEXT = "No preconditions specified."
EMPTY_ASSUMPTIONS_TEXT = "No assumptions."


def selection_limit_message(max_requirements: int) -> str:
    return f"Select up to {max_requirements} requirements for test case generation."


def selected_count_message(selected_count: int, max_requirements: int) -> str:
    return f"Selected: {selected_count} / {max_requirements}"


def extract_final_testable_requirements(results: list[dict]) -> list[dict]:
    """
    Return only final FR/NFR requirements with the required backend fields.
    Structural filtering only.
    """
    if not isinstance(results, list):
        return []

    extracted = []
    for item in results:
        if not isinstance(item, dict):
            continue

        requirement_id = item.get("id")
        requirement_text = item.get("requirement")
        classification_type = item.get("classification_type")

        if not isinstance(requirement_id, str) or not requirement_id.strip():
            continue
        if not isinstance(requirement_text, str) or not requirement_text.strip():
            continue
        if classification_type not in ALLOWED_TEST_REQUIREMENT_TYPES:
            continue

        extracted.append(
            {
                "id": requirement_id,
                "requirement": requirement_text,
                "classification_type": classification_type,
            }
        )

    return extracted


def build_test_case_payload(
    requirements: list[dict],
    project_context: str,
    mode: str,
) -> dict:
    return {
        "requirements": list(requirements),
        "project_context": project_context or None,
        "mode": mode,
    }


def _join_list(value) -> str:
    """
    list -> " | ".join(str(item))
    non-list -> "" unless already str
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return ""


def _json_string(value) -> str:
    """
    dict/list -> JSON string; None -> ""; other -> str(value)
    """
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def display_test_data_text(value) -> str:
    if isinstance(value, dict) and value:
        return _json_string(value)
    return EMPTY_TEST_DATA_TEXT


def preconditions_display_text(value) -> str:
    text = _join_list(value)
    return text if text else EMPTY_PRECONDITIONS_TEXT


def assumptions_display_text(value) -> str:
    text = _join_list(value)
    return text if text else EMPTY_ASSUMPTIONS_TEXT


def _first_non_empty(*values) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _numeric_text(value) -> str:
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def provider_signature_from_budget(budget: dict) -> str:
    """
    Build a display-only provider signature from budget metadata.
    """
    if not isinstance(budget, dict):
        return ""

    provider_used_by_stage = budget.get("provider_used_by_stage")
    if not isinstance(provider_used_by_stage, dict):
        provider_used_by_stage = {}

    provider_role_map = budget.get("provider_role_map")
    if not isinstance(provider_role_map, dict):
        provider_role_map = {}

    primary_provider = budget.get("primary_provider") or ""
    stages = ["planner", "generator", "reviewer"]
    parts = []
    for stage in stages:
        provider = (
            provider_used_by_stage.get(stage)
            or provider_role_map.get(stage)
            or primary_provider
            or "-"
        )
        parts.append(f"{stage}={provider}")
    return "|".join(parts)


def provider_metadata_display_rows(budget: dict) -> list[dict]:
    """
    Flatten provider metadata into UI-safe label/value rows.
    """
    if not isinstance(budget, dict):
        return []

    rows = []
    signature = provider_signature_from_budget(budget)
    if signature:
        rows.append({"label": "Provider strategy", "value": signature})

    rows.extend(
        [
            {
                "label": "Fallback used",
                "value": "yes" if budget.get("fallback_used") else "no",
            },
            {
                "label": "Fallback provider",
                "value": budget.get("fallback_provider") or "-",
            },
            {
                "label": "Rate-limit stage",
                "value": budget.get("rate_limit_stage") or "-",
            },
            {
                "label": "Rate-limit type",
                "value": budget.get("rate_limit_type") or "-",
            },
            {
                "label": "Provider wait seconds",
                "value": _numeric_text(budget.get("provider_wait_seconds_total")) or "0",
            },
        ]
    )
    return rows


def status_display_message(status: str) -> str:
    return STATUS_DISPLAY_MESSAGES.get(status, "Human review recommended")


def is_internal_planner_issue(reason: str | None) -> bool:
    text = (reason or "").casefold()
    return any(
        phrase in text
        for phrase in [
            "planner output could not be parsed",
            "internal planner formatting error",
            "retry generation",
        ]
    )


def bundle_status_display_message(status: str, reason: str | None = None) -> str:
    if status == "BLOCKED_MISSING_INFORMATION" and is_internal_planner_issue(reason):
        return "Generation issue. Please retry."
    return status_display_message(status)


def result_summary_metrics(result: dict) -> dict:
    if not isinstance(result, dict):
        return {
            "overall_status": "UNKNOWN",
            "overall_status_message": status_display_message("UNKNOWN"),
            "requirements_processed": 0,
            "test_cases_generated": 0,
            "needs_review_count": 0,
            "blocked_count": 0,
            "calls_used": 0,
        }

    bundles = result.get("results")
    if not isinstance(bundles, list):
        bundles = []

    test_case_count = 0
    needs_review_count = 0
    blocked_count = 0
    for bundle in bundles:
        if not isinstance(bundle, dict):
            continue
        test_cases = bundle.get("test_cases")
        if isinstance(test_cases, list):
            test_case_count += len(test_cases)
        if bundle.get("status") == "NEEDS_REVIEW":
            needs_review_count += 1
        if bundle.get("status") == "BLOCKED_MISSING_INFORMATION":
            blocked_count += 1

    budget = result.get("budget")
    if not isinstance(budget, dict):
        budget = {}

    status = result.get("status") or "UNKNOWN"
    return {
        "overall_status": status,
        "overall_status_message": status_display_message(status),
        "requirements_processed": len(bundles),
        "test_cases_generated": test_case_count,
        "needs_review_count": needs_review_count,
        "blocked_count": blocked_count,
        "calls_used": budget.get("calls_used", 0),
    }


def status_notice_kind(status: str) -> str:
    if status == "SUCCESS":
        return "success"
    if status == "NEEDS_REVIEW":
        return "warning"
    if status == "BLOCKED_MISSING_INFORMATION":
        return "info"
    if status in {"RATE_LIMITED", "PROVIDER_FAILED", "FAILED_SCHEMA_VALIDATION"}:
        return "error"
    return "warning"


def _format_steps(steps) -> str:
    """
    Convert steps list into readable CSV cell.
    """
    if not isinstance(steps, list):
        return ""

    formatted = []
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            continue

        step_number = step.get("step_number") or index
        action = step.get("action") or ""
        expected_result = step.get("expected_result") or ""
        formatted.append(f"{step_number}. {action} => {expected_result}")

    return " | ".join(formatted)


def source_basis_text(test_case: dict, traceability: dict) -> str:
    if not isinstance(test_case, dict):
        return ""
    if not isinstance(traceability, dict):
        traceability = {}

    source_basis = test_case.get("source_basis")
    if not source_basis:
        source_basis = traceability.get("source_basis")
    return _join_list(source_basis)


def _bundle_base_row(bundle: dict) -> dict:
    return {
        "requirement_id": bundle.get("requirement_id", ""),
        "requirement_text": bundle.get("requirement_text", ""),
        "requirement_type": bundle.get("requirement_type", ""),
        "bundle_status": bundle.get("status", ""),
        "bundle_missing_information": _join_list(
            bundle.get("missing_information")
        ),
        "bundle_assumptions": _join_list(bundle.get("assumptions")),
        "bundle_warnings": _join_list(bundle.get("warnings")),
        "bundle_reason": bundle.get("reason") or "",
    }


def _empty_test_case_fields() -> dict:
    return {
        "test_case_id": "",
        "title": "",
        "objective": "",
        "test_type": "",
        "technique_used": "",
        "priority": "",
        "preconditions": "",
        "test_data": "",
        "steps": "",
        "expected_result": "",
        "assumption_required": "",
        "test_case_assumptions": "",
        "traceability_requirement_id": "",
        "traceability_coverage_item": "",
        "traceability_technique_used": "",
        "source_basis": "",
    }


def _professional_row(base_row: dict, test_case: dict | None = None) -> dict:
    if not isinstance(test_case, dict):
        test_case = {}

    traceability = test_case.get("traceability")
    if not isinstance(traceability, dict):
        traceability = {}

    return {
        "Test Case ID": test_case.get("test_case_id", ""),
        "Requirement Covered": _first_non_empty(
            test_case.get("requirement_id"),
            base_row.get("requirement_id"),
        ),
        "Title": test_case.get("title", ""),
        "Type": test_case.get("test_type", ""),
        "Priority": test_case.get("priority", ""),
        "Preconditions": preconditions_display_text(test_case.get("preconditions")),
        "Steps": _format_steps(test_case.get("steps")),
        "Test Data": display_test_data_text(test_case.get("test_data")),
        "Expected Result": test_case.get("expected_result", ""),
        "Assumptions": assumptions_display_text(test_case.get("assumptions")),
        "Missing Information": base_row.get("bundle_missing_information", ""),
        "Status": base_row.get("bundle_status", ""),
        "Warnings": base_row.get("bundle_warnings", ""),
    }


def flatten_test_case_result_for_csv(result: dict) -> list[dict]:
    """
    Convert /generate_test_cases response into flat CSV rows.
    Pure structural transformation only.
    """
    if not isinstance(result, dict):
        return []

    bundles = result.get("results")
    if not isinstance(bundles, list):
        return []

    rows = []
    for bundle in bundles:
        if not isinstance(bundle, dict):
            continue

        base_row = _bundle_base_row(bundle)
        test_cases = bundle.get("test_cases")

        if not isinstance(test_cases, list) or not test_cases:
            rows.append(
                {
                    **_professional_row(base_row),
                    **base_row,
                    **_empty_test_case_fields(),
                }
            )
            continue

        for test_case in test_cases:
            if not isinstance(test_case, dict):
                continue

            traceability = test_case.get("traceability")
            if not isinstance(traceability, dict):
                traceability = {}

            rows.append(
                {
                    **_professional_row(base_row, test_case),
                    **base_row,
                    "test_case_id": test_case.get("test_case_id", ""),
                    "title": test_case.get("title", ""),
                    "objective": test_case.get("objective", ""),
                    "test_type": test_case.get("test_type", ""),
                    "technique_used": test_case.get("technique_used", ""),
                    "priority": test_case.get("priority", ""),
                    "preconditions": _join_list(test_case.get("preconditions")),
                    "test_data": _json_string(test_case.get("test_data")),
                    "steps": _format_steps(test_case.get("steps")),
                    "expected_result": test_case.get("expected_result", ""),
                    "assumption_required": _json_string(
                        test_case.get("assumption_required")
                    ),
                    "test_case_assumptions": _join_list(
                        test_case.get("assumptions")
                    ),
                    "traceability_requirement_id": traceability.get(
                        "requirement_id",
                        "",
                    ),
                    "traceability_coverage_item": traceability.get(
                        "coverage_item",
                        "",
                    ),
                    "traceability_technique_used": traceability.get(
                        "technique_used",
                        "",
                    ),
                    "source_basis": source_basis_text(test_case, traceability),
                }
            )

    return rows


def professional_csv_field_order(rows: list[dict]) -> list[str]:
    return list(PROFESSIONAL_CSV_FIELDS)


def build_test_case_json_download(result: dict) -> str:
    """
    Return pretty JSON string for download.
    """
    if not isinstance(result, dict):
        return "{}"
    return json.dumps(result, indent=2, ensure_ascii=False)
