import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.services.test_case_generation.evaluation import (
    aggregate_eval_rows,
    build_manual_review_template,
    coerce_manual_bool,
    merge_manual_review,
    normalize_manual_review_rows,
    phase12_gate_summary,
    read_csv_rows,
    write_csv_rows,
    write_json_report,
)


def base_row(eval_id="EVAL_001"):
    return {
        "eval_id": eval_id,
        "category": "simple_fr",
        "mode": "mvp_fast",
        "backend_status": "SUCCESS",
        "requirement_count": 1,
        "result_count": 1,
        "plan_count": 1,
        "total_test_cases": 1,
        "calls_used": 2,
        "estimated_calls": 2,
        "estimated_tokens": 1000,
        "schema_pass": True,
        "requirement_id_mismatch_count": 0,
        "coverage_item_mismatch_count": 0,
        "rate_limited": False,
        "provider_failed": False,
        "blocked_count": 0,
        "failed_schema_count": 0,
        "needs_review_count": 0,
        "success_count": 1,
        "manual_unsupported_invention": "",
        "manual_human_edit_needed": "",
        "manual_notes": "",
    }


def raw_result(eval_id="EVAL_001"):
    return {
        "eval_id": eval_id,
        "category": "simple_fr",
        "mode": "mvp_fast",
        "requirements": [
            {
                "id": "REQ_1",
                "requirement": "The system shall process a record.",
                "classification_type": "FR",
            }
        ],
        "result": {
            "status": "SUCCESS",
            "plans": [
                {
                    "requirement_id": "REQ_1",
                    "requirement_text": "The system shall process a record.",
                    "coverage_items": [
                        {
                            "coverage_item": "Verify record processing.",
                            "test_type": "Positive",
                            "technique_used": "Functional verification",
                            "priority": "High",
                        }
                    ],
                    "missing_information": ["Acceptance threshold is not stated."],
                    "blocking_missing_information": [],
                }
            ],
            "results": [
                {
                    "requirement_id": "REQ_1",
                    "requirement_text": "The system shall process a record.",
                    "status": "SUCCESS",
                    "reason": None,
                    "warnings": ["Review assumption."],
                    "test_cases": [
                        {
                            "test_case_id": "TC_REQ_1_001",
                            "title": "Verify processing",
                            "objective": "Confirm the record is processed.",
                            "expected_result": "The record is processed.",
                            "assumptions": ["A valid record exists."],
                        }
                    ],
                }
            ],
            "warnings": ["Top-level warning."],
            "budget": {
                "estimated_calls": 2,
                "estimated_tokens": 1000,
                "calls_used": 2,
            },
        },
    }


def passing_report(**overrides):
    report = {
        "schema_pass_rate": 1.0,
        "requirement_id_mismatch_total": 0,
        "coverage_item_mismatch_total": 0,
        "unsupported_invention_rate": 0.0,
        "rate_limit_failures": 0,
        "provider_failures": 0,
        "failed_schema_results": 0,
    }
    report.update(overrides)
    return report


def test_coerce_manual_bool_accepts_true():
    assert coerce_manual_bool("true") is True


def test_coerce_manual_bool_accepts_yes():
    assert coerce_manual_bool("yes") is True


def test_coerce_manual_bool_accepts_one():
    assert coerce_manual_bool("1") is True


def test_coerce_manual_bool_accepts_false():
    assert coerce_manual_bool("false") is False


def test_coerce_manual_bool_accepts_no():
    assert coerce_manual_bool("no") is False


def test_coerce_manual_bool_accepts_zero():
    assert coerce_manual_bool("0") is False


def test_coerce_manual_bool_keeps_empty_as_empty_string():
    assert coerce_manual_bool("") == ""


def test_coerce_manual_bool_rejects_invalid_non_empty_value():
    with pytest.raises(ValueError):
        coerce_manual_bool("maybe")


def test_read_csv_rows_handles_utf8_bom(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text(
        "\ufeffeval_id,manual_unsupported_invention\nEVAL_001,true\n",
        encoding="utf-8",
    )

    rows = read_csv_rows(str(path))

    assert rows[0]["eval_id"] == "EVAL_001"


def test_normalize_manual_review_rows_converts_manual_bool_fields():
    rows = normalize_manual_review_rows(
        [
            {
                "eval_id": "EVAL_001",
                "manual_unsupported_invention": "yes",
                "manual_human_edit_needed": "0",
            }
        ]
    )

    assert rows[0]["manual_unsupported_invention"] is True
    assert rows[0]["manual_human_edit_needed"] is False


def test_merge_manual_review_merges_by_eval_id():
    merged = merge_manual_review(
        [base_row("EVAL_001")],
        [
            {
                "eval_id": "EVAL_001",
                "manual_unsupported_invention": "false",
                "manual_human_edit_needed": "true",
                "manual_notes": "Reviewed.",
            }
        ],
    )

    assert merged[0]["manual_unsupported_invention"] is False
    assert merged[0]["manual_human_edit_needed"] is True
    assert merged[0]["manual_notes"] == "Reviewed."


def test_merge_manual_review_preserves_rows_without_matching_manual_row():
    row = base_row("EVAL_001")
    row["manual_notes"] = "Existing note."

    merged = merge_manual_review([row], [{"eval_id": "EVAL_OTHER"}])

    assert merged[0]["manual_notes"] == "Existing note."
    assert merged[0]["manual_unsupported_invention"] == ""


def test_build_manual_review_template_creates_one_row_per_raw_result():
    template = build_manual_review_template(
        [raw_result("EVAL_001"), raw_result("EVAL_002")],
        [base_row("EVAL_001"), base_row("EVAL_002")],
    )

    assert len(template) == 2


def test_template_includes_requirement_text():
    template = build_manual_review_template([raw_result()], [base_row()])

    assert "process a record" in template[0]["requirement_text"]


def test_template_includes_plan_summary():
    template = build_manual_review_template([raw_result()], [base_row()])

    assert "Verify record processing" in template[0]["plan_summary"]
    assert "Acceptance threshold" in template[0]["plan_summary"]


def test_template_includes_test_case_summary():
    template = build_manual_review_template([raw_result()], [base_row()])

    assert "TC_REQ_1_001" in template[0]["test_case_summary"]
    assert "The record is processed" in template[0]["test_case_summary"]


def test_template_includes_manual_fields_empty():
    template = build_manual_review_template([raw_result()], [base_row()])

    assert template[0]["manual_unsupported_invention"] == ""
    assert template[0]["manual_human_edit_needed"] == ""
    assert template[0]["manual_notes"] == ""


def test_aggregate_reviewed_rows_computes_unsupported_invention_rate():
    rows = [base_row("EVAL_001"), base_row("EVAL_002")]
    rows[0]["manual_unsupported_invention"] = True
    rows[1]["manual_unsupported_invention"] = False

    assert aggregate_eval_rows(rows)["unsupported_invention_rate"] == 0.5


def test_phase12_gate_summary_fails_when_unsupported_invention_rate_is_none():
    summary = phase12_gate_summary(passing_report(unsupported_invention_rate=None))

    assert summary["phase12_gate_passed"] is False
    assert summary["required_gates"]["unsupported_invention_lte_5_percent"] is False


def test_phase12_gate_summary_passes_when_all_gates_pass():
    summary = phase12_gate_summary(passing_report())

    assert summary["phase12_gate_passed"] is True


def test_phase12_gate_summary_fails_when_provider_failures_above_zero():
    summary = phase12_gate_summary(passing_report(provider_failures=1))

    assert summary["phase12_gate_passed"] is False
    assert summary["required_gates"]["no_provider_failures"] is False


def test_phase12_gate_summary_fails_when_failed_schema_results_above_zero():
    summary = phase12_gate_summary(passing_report(failed_schema_results=1))

    assert summary["phase12_gate_passed"] is False
    assert summary["required_gates"]["no_failed_schema_results"] is False


def test_phase12_gate_summary_fails_when_unsupported_invention_above_five_percent():
    summary = phase12_gate_summary(passing_report(unsupported_invention_rate=0.06))

    assert summary["phase12_gate_passed"] is False
    assert summary["required_gates"]["unsupported_invention_lte_5_percent"] is False


def test_review_cli_make_template_creates_csv(tmp_path):
    rows_path = tmp_path / "rows.csv"
    raw_path = tmp_path / "raw.json"
    manual_path = tmp_path / "manual.csv"
    write_csv_rows(str(rows_path), [base_row()])
    write_json_report(str(raw_path), [raw_result()])

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/review_test_case_evaluation.py",
            "--make-template",
            "--rows",
            str(rows_path),
            "--raw-results",
            str(raw_path),
            "--manual-review",
            str(manual_path),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert manual_path.exists()
    assert read_csv_rows(str(manual_path))[0]["eval_id"] == "EVAL_001"


def test_review_cli_aggregate_reviewed_creates_final_json(tmp_path):
    rows_path = tmp_path / "rows.csv"
    manual_path = tmp_path / "manual.csv"
    reviewed_path = tmp_path / "reviewed.csv"
    final_path = tmp_path / "final.json"
    write_csv_rows(str(rows_path), [base_row()])
    write_csv_rows(
        str(manual_path),
        [
            {
                "eval_id": "EVAL_001",
                "manual_unsupported_invention": "false",
                "manual_human_edit_needed": "false",
                "manual_notes": "Reviewed.",
            }
        ],
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/review_test_case_evaluation.py",
            "--aggregate-reviewed",
            "--rows",
            str(rows_path),
            "--manual-review",
            str(manual_path),
            "--reviewed-rows-output",
            str(reviewed_path),
            "--final-report-output",
            str(final_path),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    report = json.loads(final_path.read_text())
    assert report["aggregate"]["unsupported_invention_rate"] == 0.0
    assert report["phase12_gate"]["phase12_gate_passed"] is True


def test_review_cli_with_no_command_exits_non_zero():
    completed = subprocess.run(
        [sys.executable, "scripts/review_test_case_evaluation.py"],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0


def test_no_live_llm_imports_in_review_script():
    text = Path("scripts/review_test_case_evaluation.py").read_text()

    forbidden = [
        "Test" + "CaseEngine",
        "call" + "_llm",
        "Groq" + "Provider",
        "requests" + ".",
        "httpx" + ".",
    ]

    for fragment in forbidden:
        assert fragment not in text


def test_no_keyword_domain_branching_in_phase12g_files():
    combined = "\n".join(
        Path(path).read_text()
        for path in [
            "app/services/test_case_generation/evaluation.py",
            "scripts/review_test_case_evaluation.py",
        ]
    )
    forbidden = [
        "requirement" + "." + "low" + "er(",
        'if "' + "login" + '" in',
        'if "' + "password" + '" in',
        'if "' + "payment" + '" in',
        'if "' + "security" + '" in',
        "keyword-to" + "-test-type maps",
        "keyword-to" + "-technique maps",
        "hardcoded business" + "/domain routing",
        "fu" + "zzy",
        "sim" + "ilarity",
        "con" + "tains(",
        "start" + "swith(",
        "." + "low" + "er(",
    ]

    for fragment in forbidden:
        assert fragment not in combined

