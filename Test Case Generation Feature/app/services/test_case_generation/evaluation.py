import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ALLOWED_EVAL_MODES = {"mvp_fast", "balanced"}
ALLOWED_EVAL_REQUIREMENT_TYPES = {"FR", "NFR"}


def load_eval_dataset(path: str) -> list[dict]:
    """
    Load evaluation dataset JSON.
    Validate top-level list.
    """
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("evaluation dataset must be a list")

    return data


def validate_eval_item(item: dict) -> list[str]:
    """
    Return list of validation errors.
    Structural validation only.
    """
    errors: list[str] = []

    if not isinstance(item, dict):
        return ["item must be a dict"]

    if not _non_empty_string(item.get("eval_id")):
        errors.append("eval_id must be a non-empty string")

    if not _non_empty_string(item.get("category")):
        errors.append("category must be a non-empty string")

    mode = item.get("mode")
    if mode not in ALLOWED_EVAL_MODES:
        errors.append("mode must be mvp_fast or balanced")

    project_context = item.get("project_context")
    if project_context is not None and not isinstance(project_context, str):
        errors.append("project_context must be string or null")

    requirements = item.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("requirements must be a non-empty list")
    elif not all(isinstance(requirement, dict) for requirement in requirements):
        errors.append("requirements must contain only dict items")
    else:
        for index, requirement in enumerate(requirements, 1):
            prefix = f"requirements[{index}]"
            if not _non_empty_string(requirement.get("id")):
                errors.append(f"{prefix}.id must be a non-empty string")
            if not _non_empty_string(requirement.get("requirement")):
                errors.append(f"{prefix}.requirement must be a non-empty string")
            if requirement.get("classification_type") not in ALLOWED_EVAL_REQUIREMENT_TYPES:
                errors.append(f"{prefix}.classification_type must be FR or NFR")

    expected = item.get("expected")
    if not isinstance(expected, dict):
        errors.append("expected must be a dict")
    else:
        if not isinstance(expected.get("should_generate"), bool):
            errors.append("expected.should_generate must be bool")
        if not _non_empty_string(expected.get("expected_status_family")):
            errors.append("expected.expected_status_family must be a non-empty string")

    return errors


def validate_eval_dataset(items: list[dict]) -> dict:
    """
    Return dataset validation summary.
    """
    errors: list[str] = []
    category_counts: Counter = Counter()

    if not isinstance(items, list):
        return {
            "valid": False,
            "item_count": 0,
            "errors": ["dataset must be a list"],
            "category_counts": {},
        }

    for index, item in enumerate(items, 1):
        if isinstance(item, dict) and _non_empty_string(item.get("category")):
            category_counts[item["category"]] += 1

        for error in validate_eval_item(item):
            eval_id = item.get("eval_id") if isinstance(item, dict) else None
            label = eval_id if _non_empty_string(eval_id) else f"item_{index}"
            errors.append(f"{label}: {error}")

    return {
        "valid": not errors,
        "item_count": len(items),
        "errors": errors,
        "category_counts": dict(category_counts),
    }


def summarize_generation_result(eval_item: dict, result: dict) -> dict:
    """
    Convert one /generate_test_cases result into one compact evaluation row.
    Pure structural summarization only.
    """
    requirements = eval_item.get("requirements", [])
    requirement_ids = {
        requirement.get("id")
        for requirement in requirements
        if isinstance(requirement, dict)
    }

    schema_pass = _result_has_expected_shape(result)
    results = result.get("results", []) if isinstance(result, dict) else []
    plans = result.get("plans", []) if isinstance(result, dict) else []
    budget = result.get("budget", {}) if isinstance(result, dict) else {}
    backend_status = result.get("status") if isinstance(result, dict) else None
    provider_metadata = _provider_metadata_from_budget(budget)

    plan_coverage = _coverage_by_requirement(plans)

    total_test_cases = 0
    requirement_id_mismatch_count = 0
    coverage_item_mismatch_count = 0
    status_counts: Counter = Counter()

    for bundle in results if isinstance(results, list) else []:
        if not isinstance(bundle, dict):
            continue

        bundle_requirement_id = bundle.get("requirement_id")
        if bundle_requirement_id not in requirement_ids:
            requirement_id_mismatch_count += 1

        status = bundle.get("status")
        if isinstance(status, str):
            status_counts[status] += 1

        test_cases = bundle.get("test_cases", [])
        if not isinstance(test_cases, list):
            continue

        total_test_cases += len(test_cases)
        allowed_coverage = plan_coverage.get(bundle_requirement_id, set())
        for test_case in test_cases:
            if not isinstance(test_case, dict):
                continue
            traceability = test_case.get("traceability", {})
            coverage_item = (
                traceability.get("coverage_item")
                if isinstance(traceability, dict)
                else None
            )
            if coverage_item not in allowed_coverage:
                coverage_item_mismatch_count += 1

    return {
        "eval_id": eval_item.get("eval_id"),
        "category": eval_item.get("category"),
        "mode": eval_item.get("mode", "mvp_fast"),
        "backend_status": backend_status,
        "requirement_count": len(requirements) if isinstance(requirements, list) else 0,
        "result_count": len(results) if isinstance(results, list) else 0,
        "plan_count": len(plans) if isinstance(plans, list) else 0,
        "total_test_cases": total_test_cases,
        "calls_used": _numeric_value(budget.get("calls_used")),
        "estimated_calls": _numeric_value(budget.get("estimated_calls")),
        "estimated_tokens": _numeric_value(budget.get("estimated_tokens")),
        "primary_provider": provider_metadata["primary_provider"],
        "strict_provider": provider_metadata["strict_provider"],
        "provider_role_map_json": provider_metadata["provider_role_map_json"],
        "provider_used_by_stage_json": provider_metadata["provider_used_by_stage_json"],
        "planner_provider": provider_metadata["planner_provider"],
        "generator_provider": provider_metadata["generator_provider"],
        "reviewer_provider": provider_metadata["reviewer_provider"],
        "fallback_used": provider_metadata["fallback_used"],
        "fallback_provider": provider_metadata["fallback_provider"],
        "fallback_reason": provider_metadata["fallback_reason"],
        "rate_limit_stage": provider_metadata["rate_limit_stage"],
        "rate_limit_type": provider_metadata["rate_limit_type"],
        "retry_attempts": provider_metadata["retry_attempts"],
        "provider_wait_seconds_total": provider_metadata[
            "provider_wait_seconds_total"
        ],
        "provider_wait_by_stage_json": provider_metadata[
            "provider_wait_by_stage_json"
        ],
        "provider_wait_by_provider_json": provider_metadata[
            "provider_wait_by_provider_json"
        ],
        "provider_signature": provider_metadata["provider_signature"],
        "schema_pass": schema_pass,
        "requirement_id_mismatch_count": requirement_id_mismatch_count,
        "coverage_item_mismatch_count": coverage_item_mismatch_count,
        "rate_limited": backend_status == "RATE_LIMITED",
        "provider_failed": backend_status == "PROVIDER_FAILED",
        "blocked_count": status_counts["BLOCKED_MISSING_INFORMATION"],
        "failed_schema_count": status_counts["FAILED_SCHEMA_VALIDATION"],
        "needs_review_count": status_counts["NEEDS_REVIEW"],
        "success_count": status_counts["SUCCESS"],
        "manual_unsupported_invention": "",
        "manual_human_edit_needed": "",
        "manual_notes": "",
    }


def aggregate_eval_rows(rows: list[dict]) -> dict:
    """
    Aggregate quality metrics.
    """
    total = len(rows)
    schema_pass_count = sum(
        1 for row in rows if _bool_value(row.get("schema_pass")) is True
    )
    requirement_id_mismatch_total = sum(
        int(row.get("requirement_id_mismatch_count") or 0) for row in rows
    )
    coverage_item_mismatch_total = sum(
        int(row.get("coverage_item_mismatch_count") or 0) for row in rows
    )
    requirement_count_total = sum(int(row.get("requirement_count") or 0) for row in rows)
    total_test_cases = sum(int(row.get("total_test_cases") or 0) for row in rows)

    reviewed_rows = [
        row
        for row in rows
        if isinstance(row.get("manual_unsupported_invention"), bool)
    ]
    unsupported_invention_rate = None
    if reviewed_rows:
        unsupported_count = sum(
            1 for row in reviewed_rows if row.get("manual_unsupported_invention") is True
        )
        unsupported_invention_rate = unsupported_count / len(reviewed_rows)

    status_counts: Counter = Counter()
    category_counts: Counter = Counter()
    provider_signature_counts: Counter = Counter()
    primary_provider_counts: Counter = Counter()
    planner_provider_counts: Counter = Counter()
    generator_provider_counts: Counter = Counter()
    reviewer_provider_counts: Counter = Counter()
    fallback_provider_counts: Counter = Counter()
    rate_limit_type_counts: Counter = Counter()
    provider_wait_seconds_total = 0.0
    provider_wait_by_stage: Counter = Counter()
    provider_wait_by_provider: Counter = Counter()
    for row in rows:
        if _non_empty_string(row.get("backend_status")):
            status_counts[row["backend_status"]] += 1
        if _non_empty_string(row.get("category")):
            category_counts[row["category"]] += 1
        if _non_empty_string(row.get("provider_signature")):
            provider_signature_counts[row["provider_signature"]] += 1
        if _non_empty_string(row.get("primary_provider")):
            primary_provider_counts[row["primary_provider"]] += 1
        if _non_empty_string(row.get("planner_provider")):
            planner_provider_counts[row["planner_provider"]] += 1
        if _non_empty_string(row.get("generator_provider")):
            generator_provider_counts[row["generator_provider"]] += 1
        if _non_empty_string(row.get("reviewer_provider")):
            reviewer_provider_counts[row["reviewer_provider"]] += 1
        if _non_empty_string(row.get("fallback_provider")):
            fallback_provider_counts[row["fallback_provider"]] += 1
        if _non_empty_string(row.get("rate_limit_type")):
            rate_limit_type_counts[row["rate_limit_type"]] += 1
        provider_wait_seconds_total += float(
            _numeric_value(row.get("provider_wait_seconds_total"))
        )
        provider_wait_by_stage.update(
            _json_numeric_mapping(row.get("provider_wait_by_stage_json"))
        )
        provider_wait_by_provider.update(
            _json_numeric_mapping(row.get("provider_wait_by_provider_json"))
        )

    schema_pass_rate = schema_pass_count / total if total else 0.0
    average_test_cases_per_requirement = (
        total_test_cases / requirement_count_total if requirement_count_total else 0.0
    )
    average_calls_used = _average_numeric(rows, "calls_used")
    average_estimated_tokens = _average_numeric(rows, "estimated_tokens")

    return {
        "total_eval_items": total,
        "schema_pass_rate": schema_pass_rate,
        "requirement_id_mismatch_total": requirement_id_mismatch_total,
        "coverage_item_mismatch_total": coverage_item_mismatch_total,
        "unsupported_invention_rate": unsupported_invention_rate,
        "average_test_cases_per_requirement": average_test_cases_per_requirement,
        "average_calls_used": average_calls_used,
        "average_estimated_tokens": average_estimated_tokens,
        "rate_limit_failures": sum(
            1 for row in rows if _bool_value(row.get("rate_limited")) is True
        ),
        "provider_failures": sum(
            1 for row in rows if _bool_value(row.get("provider_failed")) is True
        ),
        "blocked_results": sum(int(row.get("blocked_count") or 0) for row in rows),
        "failed_schema_results": sum(int(row.get("failed_schema_count") or 0) for row in rows),
        "status_counts": dict(status_counts),
        "category_counts": dict(category_counts),
        "provider_signature_counts": dict(provider_signature_counts),
        "primary_provider_counts": dict(primary_provider_counts),
        "planner_provider_counts": dict(planner_provider_counts),
        "generator_provider_counts": dict(generator_provider_counts),
        "reviewer_provider_counts": dict(reviewer_provider_counts),
        "fallback_used_count": sum(
            1 for row in rows if _bool_value(row.get("fallback_used")) is True
        ),
        "fallback_provider_counts": dict(fallback_provider_counts),
        "rate_limit_type_counts": dict(rate_limit_type_counts),
        "provider_wait_seconds_total": provider_wait_seconds_total,
        "provider_wait_by_stage": dict(provider_wait_by_stage),
        "provider_wait_by_provider": dict(provider_wait_by_provider),
        "quality_gates": {
            "schema_pass_rate_gte_95": schema_pass_rate >= 0.95,
            "requirement_id_mismatch_zero": requirement_id_mismatch_total == 0,
            "coverage_item_mismatch_zero": coverage_item_mismatch_total == 0,
            "unsupported_invention_lte_5_percent": (
                None
                if unsupported_invention_rate is None
                else unsupported_invention_rate <= 0.05
            ),
            "no_rate_limit_failures": not any(
                _bool_value(row.get("rate_limited")) is True for row in rows
            ),
        },
    }


def write_json_report(path: str, report: dict) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)
        file.write("\n")


def write_csv_rows(path: str, rows: list[dict]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _csv_fieldnames(rows)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: str) -> list[dict]:
    """
    Read CSV rows as list[dict].
    """
    with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def coerce_manual_bool(value):
    """
    Convert manual CSV values to bool/empty.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False

    text = str(value).strip()
    if text == "":
        return ""

    folded = text.casefold()
    if folded in {"true", "yes", "y", "1"}:
        return True
    if folded in {"false", "no", "n", "0"}:
        return False
    raise ValueError(f"invalid manual boolean value: {value!r}")


def normalize_manual_review_rows(rows: list[dict]) -> list[dict]:
    """
    Convert manual review boolean fields into bool or empty string.
    """
    normalized: list[dict] = []
    for row in rows:
        normalized_row = dict(row)
        normalized_row["manual_unsupported_invention"] = coerce_manual_bool(
            normalized_row.get("manual_unsupported_invention")
        )
        normalized_row["manual_human_edit_needed"] = coerce_manual_bool(
            normalized_row.get("manual_human_edit_needed")
        )
        normalized.append(normalized_row)
    return normalized


def build_manual_review_template(raw_results: list[dict], rows: list[dict]) -> list[dict]:
    """
    Build a human-friendly review CSV.
    """
    rows_by_eval_id = {
        row.get("eval_id"): row
        for row in rows
        if isinstance(row, dict) and row.get("eval_id") is not None
    }
    template_rows: list[dict] = []

    for raw_result in raw_results:
        if not isinstance(raw_result, dict):
            continue

        eval_id = raw_result.get("eval_id")
        row = rows_by_eval_id.get(eval_id, {})
        result = raw_result.get("result", {})
        if not isinstance(result, dict):
            result = {}

        template_rows.append(
            {
                "eval_id": eval_id,
                "category": raw_result.get("category") or row.get("category", ""),
                "backend_status": row.get("backend_status")
                or result.get("status")
                or "",
                "total_test_cases": row.get("total_test_cases", ""),
                "provider_signature": row.get("provider_signature", ""),
                "planner_provider": row.get("planner_provider", ""),
                "generator_provider": row.get("generator_provider", ""),
                "reviewer_provider": row.get("reviewer_provider", ""),
                "fallback_used": row.get("fallback_used", ""),
                "fallback_provider": row.get("fallback_provider", ""),
                "requirement_text": _manual_review_requirement_text(raw_result),
                "plan_summary": _manual_review_plan_summary(result.get("plans", [])),
                "test_case_summary": _manual_review_test_case_summary(
                    result.get("results", [])
                ),
                "warnings_summary": _manual_review_warnings_summary(result),
                "manual_unsupported_invention": "",
                "manual_human_edit_needed": "",
                "manual_notes": "",
            }
        )

    return template_rows


def merge_manual_review(rows: list[dict], manual_rows: list[dict]) -> list[dict]:
    """
    Merge manual review decisions back into evaluation rows by eval_id.
    """
    normalized_manual_rows = normalize_manual_review_rows(manual_rows)
    manual_by_eval_id = {
        row.get("eval_id"): row
        for row in normalized_manual_rows
        if isinstance(row, dict) and row.get("eval_id") is not None
    }

    merged_rows: list[dict] = []
    for row in rows:
        merged_row = dict(row)
        manual_row = manual_by_eval_id.get(row.get("eval_id"))
        if manual_row is not None:
            merged_row["manual_unsupported_invention"] = manual_row.get(
                "manual_unsupported_invention", ""
            )
            merged_row["manual_human_edit_needed"] = manual_row.get(
                "manual_human_edit_needed", ""
            )
            merged_row["manual_notes"] = manual_row.get("manual_notes", "")
        else:
            merged_row["manual_unsupported_invention"] = coerce_manual_bool(
                merged_row.get("manual_unsupported_invention")
            )
            merged_row["manual_human_edit_needed"] = coerce_manual_bool(
                merged_row.get("manual_human_edit_needed")
            )
        merged_rows.append(merged_row)

    return merged_rows


def phase12_gate_summary(report: dict) -> dict:
    """
    Build final gate summary from aggregate_eval_rows output.
    """
    unsupported_rate = report.get("unsupported_invention_rate")
    required_gates = {
        "schema_pass_rate_gte_95": report.get("schema_pass_rate", 0) >= 0.95,
        "requirement_id_mismatch_zero": (
            report.get("requirement_id_mismatch_total") == 0
        ),
        "coverage_item_mismatch_zero": (
            report.get("coverage_item_mismatch_total") == 0
        ),
        "unsupported_invention_lte_5_percent": (
            False if unsupported_rate is None else unsupported_rate <= 0.05
        ),
        "no_rate_limit_failures": report.get("rate_limit_failures") == 0,
        "no_provider_failures": report.get("provider_failures") == 0,
        "no_failed_schema_results": report.get("failed_schema_results") == 0,
    }

    notes: list[str] = []
    if unsupported_rate is None:
        notes.append("Manual unsupported invention review is not complete.")
    for gate_name, passed in required_gates.items():
        if not passed:
            notes.append(f"{gate_name} failed")

    return {
        "phase12_gate_passed": all(required_gates.values()),
        "required_gates": required_gates,
        "notes": notes,
    }


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _numeric_value(value: Any) -> int | float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return 0
        try:
            numeric = float(text)
        except ValueError:
            return 0
        return int(numeric) if numeric.is_integer() else numeric
    return 0


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        folded = value.strip().casefold()
        if folded in {"true", "yes", "y", "1"}:
            return True
    return False


def _average_numeric(rows: list[dict], field_name: str) -> float:
    if not rows:
        return 0.0
    return sum(_numeric_value(row.get(field_name)) for row in rows) / len(rows)


def _provider_metadata_from_budget(budget: dict) -> dict:
    if not isinstance(budget, dict):
        budget = {}

    primary_provider = _compact_text(budget.get("primary_provider"))
    provider_used_by_stage = (
        budget.get("provider_used_by_stage")
        if isinstance(budget.get("provider_used_by_stage"), dict)
        else {}
    )
    provider_role_map = (
        budget.get("provider_role_map")
        if isinstance(budget.get("provider_role_map"), dict)
        else {}
    )

    planner_provider = _stage_provider(
        "planner",
        provider_used_by_stage,
        provider_role_map,
        primary_provider,
    )
    generator_provider = _stage_provider(
        "generator",
        provider_used_by_stage,
        provider_role_map,
        primary_provider,
    )
    reviewer_provider = _stage_provider(
        "reviewer",
        provider_used_by_stage,
        provider_role_map,
        primary_provider,
    )

    return {
        "primary_provider": primary_provider,
        "strict_provider": budget.get("strict_provider"),
        "provider_role_map_json": json.dumps(
            provider_role_map,
            sort_keys=True,
            ensure_ascii=False,
        ),
        "provider_used_by_stage_json": json.dumps(
            provider_used_by_stage,
            sort_keys=True,
            ensure_ascii=False,
        ),
        "planner_provider": planner_provider,
        "generator_provider": generator_provider,
        "reviewer_provider": reviewer_provider,
        "fallback_used": budget.get("fallback_used", False),
        "fallback_provider": _compact_text(budget.get("fallback_provider")),
        "fallback_reason": _compact_text(budget.get("fallback_reason")),
        "rate_limit_stage": _compact_text(budget.get("rate_limit_stage")),
        "rate_limit_type": _compact_text(budget.get("rate_limit_type")),
        "retry_attempts": _numeric_value(budget.get("retry_attempts")),
        "provider_wait_seconds_total": _numeric_value(
            budget.get("provider_wait_seconds_total")
        ),
        "provider_wait_by_stage_json": json.dumps(
            _numeric_dict(budget.get("provider_wait_by_stage")),
            sort_keys=True,
            ensure_ascii=False,
        ),
        "provider_wait_by_provider_json": json.dumps(
            _numeric_dict(budget.get("provider_wait_by_provider")),
            sort_keys=True,
            ensure_ascii=False,
        ),
        "provider_signature": (
            f"planner={planner_provider}|"
            f"generator={generator_provider}|"
            f"reviewer={reviewer_provider}"
        ),
    }


def _stage_provider(
    stage: str,
    provider_used_by_stage: dict,
    provider_role_map: dict,
    primary_provider: str,
) -> str:
    used = _compact_text(provider_used_by_stage.get(stage))
    if used:
        return used
    role = _compact_text(provider_role_map.get(stage))
    if role:
        return role
    return primary_provider


def _numeric_dict(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    output = {}
    for key, item in value.items():
        if _non_empty_string(key):
            output[key] = _numeric_value(item)
    return output


def _json_numeric_mapping(value: Any) -> dict:
    if isinstance(value, dict):
        return _numeric_dict(value)
    if not _non_empty_string(value):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return _numeric_dict(parsed)


def _result_has_expected_shape(result: dict) -> bool:
    if not isinstance(result, dict):
        return False

    if not _non_empty_string(result.get("status")):
        return False
    if not isinstance(result.get("results"), list):
        return False
    if not isinstance(result.get("plans"), list):
        return False

    budget = result.get("budget")
    if not isinstance(budget, dict):
        return False

    for field_name in ("calls_used", "estimated_calls", "estimated_tokens"):
        if field_name not in budget or not isinstance(budget[field_name], (int, float)):
            return False

    return True


def _coverage_by_requirement(plans: list) -> dict[str, set[str]]:
    coverage_by_requirement: dict[str, set[str]] = {}

    for plan in plans if isinstance(plans, list) else []:
        if not isinstance(plan, dict):
            continue
        requirement_id = plan.get("requirement_id")
        coverage_items = plan.get("coverage_items", [])
        if not isinstance(requirement_id, str) or not isinstance(coverage_items, list):
            continue

        coverage_by_requirement[requirement_id] = {
            item.get("coverage_item")
            for item in coverage_items
            if isinstance(item, dict) and _non_empty_string(item.get("coverage_item"))
        }

    return coverage_by_requirement


def _manual_review_requirement_text(raw_result: dict) -> str:
    requirements = raw_result.get("requirements", [])
    if isinstance(requirements, list):
        requirement_texts = [
            requirement.get("requirement", "")
            for requirement in requirements
            if isinstance(requirement, dict)
            and _non_empty_string(requirement.get("requirement"))
        ]
        if requirement_texts:
            return " | ".join(requirement_texts)

    result = raw_result.get("result", {})
    if not isinstance(result, dict):
        return ""

    plans = result.get("plans", [])
    if isinstance(plans, list):
        plan_texts = [
            plan.get("requirement_text", "")
            for plan in plans
            if isinstance(plan, dict)
            and _non_empty_string(plan.get("requirement_text"))
        ]
        if plan_texts:
            return " | ".join(plan_texts)

    bundles = result.get("results", [])
    if isinstance(bundles, list):
        bundle_texts = [
            bundle.get("requirement_text", "")
            for bundle in bundles
            if isinstance(bundle, dict)
            and _non_empty_string(bundle.get("requirement_text"))
        ]
        if bundle_texts:
            return " | ".join(bundle_texts)

    return ""


def _manual_review_plan_summary(plans: list) -> str:
    parts: list[str] = []
    for plan in plans if isinstance(plans, list) else []:
        if not isinstance(plan, dict):
            continue
        requirement_id = plan.get("requirement_id", "")
        coverage_items = plan.get("coverage_items", [])
        for coverage_item in coverage_items if isinstance(coverage_items, list) else []:
            if not isinstance(coverage_item, dict):
                continue
            parts.append(
                " | ".join(
                    _compact_text(value)
                    for value in [
                        requirement_id,
                        coverage_item.get("coverage_item", ""),
                        coverage_item.get("test_type", ""),
                        coverage_item.get("technique_used", ""),
                        coverage_item.get("priority", ""),
                    ]
                    if _compact_text(value)
                )
            )

        missing_information = plan.get("missing_information", [])
        if isinstance(missing_information, list) and missing_information:
            parts.append(
                f"{requirement_id} missing: "
                + "; ".join(_compact_text(item) for item in missing_information)
            )
        blocking_missing_information = plan.get("blocking_missing_information", [])
        if (
            isinstance(blocking_missing_information, list)
            and blocking_missing_information
        ):
            parts.append(
                f"{requirement_id} blocking: "
                + "; ".join(
                    _compact_text(item) for item in blocking_missing_information
                )
            )

    return "\n".join(part for part in parts if part)


def _manual_review_test_case_summary(bundles: list) -> str:
    parts: list[str] = []
    for bundle in bundles if isinstance(bundles, list) else []:
        if not isinstance(bundle, dict):
            continue
        test_cases = bundle.get("test_cases", [])
        for test_case in test_cases if isinstance(test_cases, list) else []:
            if not isinstance(test_case, dict):
                continue
            assumptions = test_case.get("assumptions", [])
            assumptions_text = (
                "; ".join(_compact_text(item) for item in assumptions)
                if isinstance(assumptions, list)
                else _compact_text(assumptions)
            )
            parts.append(
                " | ".join(
                    _compact_text(value)
                    for value in [
                        test_case.get("test_case_id", ""),
                        test_case.get("title", ""),
                        test_case.get("objective", ""),
                        test_case.get("expected_result", ""),
                        f"assumptions: {assumptions_text}"
                        if assumptions_text
                        else "",
                    ]
                    if _compact_text(value)
                )
            )
    return "\n".join(part for part in parts if part)


def _manual_review_warnings_summary(result: dict) -> str:
    parts: list[str] = []
    warnings = result.get("warnings", [])
    if isinstance(warnings, list):
        parts.extend(_compact_text(item) for item in warnings)

    bundles = result.get("results", [])
    for bundle in bundles if isinstance(bundles, list) else []:
        if not isinstance(bundle, dict):
            continue
        requirement_id = bundle.get("requirement_id", "")
        reason = bundle.get("reason")
        if _compact_text(reason):
            parts.append(f"{requirement_id} reason: {_compact_text(reason)}")
        bundle_warnings = bundle.get("warnings", [])
        if isinstance(bundle_warnings, list):
            for warning in bundle_warnings:
                parts.append(f"{requirement_id} warning: {_compact_text(warning)}")

    return "\n".join(part for part in parts if part)


def _compact_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return " ".join(str(value).split())


def _csv_fieldnames(rows: list[dict]) -> list[str]:
    if not rows:
        return [
            "eval_id",
            "category",
            "mode",
            "backend_status",
            "schema_pass",
            "manual_unsupported_invention",
            "manual_human_edit_needed",
            "manual_notes",
        ]

    fieldnames: list[str] = []
    for row in rows:
        for field_name in row:
            if field_name not in fieldnames:
                fieldnames.append(field_name)
    return fieldnames
