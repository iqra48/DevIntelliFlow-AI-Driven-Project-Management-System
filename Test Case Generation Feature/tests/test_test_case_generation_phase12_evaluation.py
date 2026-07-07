import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from app.services.test_case_generation.evaluation import (
    aggregate_eval_rows,
    load_eval_dataset,
    summarize_generation_result,
    validate_eval_dataset,
    validate_eval_item,
    write_csv_rows,
    write_json_report,
)


DATASET_PATH = Path("eval/test_case_generation_eval_dataset.json")


def sample_eval_item():
    return {
        "eval_id": "EVAL_TEST_001",
        "category": "simple_fr",
        "mode": "mvp_fast",
        "project_context": "Generic web application.",
        "requirements": [
            {
                "id": "REQ_1",
                "requirement": "The system shall process a record.",
                "classification_type": "FR",
            }
        ],
        "expected": {
            "should_generate": True,
            "expected_status_family": "SUCCESS_OR_NEEDS_REVIEW",
        },
    }


def sample_result(
    status="SUCCESS",
    bundle_requirement_id="REQ_1",
    coverage_item="Verify stated behavior.",
):
    return {
        "status": status,
        "results": [
            {
                "requirement_id": bundle_requirement_id,
                "requirement_text": "The system shall process a record.",
                "requirement_type": "FR",
                "status": status,
                "test_cases": [
                    {
                        "test_case_id": "TC_REQ_1_001",
                        "requirement_id": bundle_requirement_id,
                        "title": "Verify planned behavior",
                        "objective": "Confirm behavior.",
                        "test_type": "Positive",
                        "technique_used": "Functional verification",
                        "priority": "High",
                        "preconditions": [],
                        "test_data": {},
                        "steps": [
                            {
                                "step_number": 1,
                                "action": "Perform action.",
                                "expected_result": "Expected result appears.",
                            }
                        ],
                        "expected_result": "Expected result appears.",
                        "assumption_required": False,
                        "assumptions": [],
                        "traceability": {
                            "requirement_id": bundle_requirement_id,
                            "coverage_item": coverage_item,
                            "technique_used": "Functional verification",
                        },
                    }
                ],
                "missing_information": [],
                "assumptions": [],
                "warnings": [],
                "reason": None,
            }
        ],
        "plans": [
            {
                "requirement_id": "REQ_1",
                "requirement_text": "The system shall process a record.",
                "requirement_type": "FR",
                "testable": True,
                "safe_to_generate": True,
                "risk_level": "Medium",
                "ambiguity_level": "Low",
                "blocking_missing_information": [],
                "missing_information": [],
                "coverage_items": [
                    {
                        "coverage_item": "Verify stated behavior.",
                        "test_type": "Positive",
                        "technique_used": "Functional verification",
                        "priority": "High",
                        "rationale": "Covers planned behavior.",
                    }
                ],
                "recommended_test_case_count": 1,
                "assumptions": [],
            }
        ],
        "warnings": [],
        "budget": {
            "mode": "mvp_fast",
            "estimated_calls": 2,
            "estimated_tokens": 1200,
            "calls_used": 2,
        },
    }


def dataset_items():
    return load_eval_dataset(str(DATASET_PATH))


def test_eval_dataset_file_exists():
    assert DATASET_PATH.exists()


def test_dataset_has_exactly_45_items():
    assert len(dataset_items()) == 45


def test_dataset_has_10_simple_fr():
    assert Counter(item["category"] for item in dataset_items())["simple_fr"] == 10


def test_dataset_has_10_validation_rule_fr():
    assert Counter(item["category"] for item in dataset_items())["validation_rule_fr"] == 10


def test_dataset_has_10_login_security_fr():
    assert Counter(item["category"] for item in dataset_items())["login_security_fr"] == 10


def test_dataset_has_10_nfr():
    assert Counter(item["category"] for item in dataset_items())["nfr"] == 10


def test_dataset_has_5_vague_blocked():
    assert Counter(item["category"] for item in dataset_items())["vague_blocked"] == 5


def test_validate_eval_dataset_returns_valid_true_for_dataset():
    summary = validate_eval_dataset(dataset_items())

    assert summary["valid"] is True
    assert summary["item_count"] == 45


def test_validate_eval_item_catches_missing_eval_id():
    item = sample_eval_item()
    del item["eval_id"]

    assert any("eval_id" in error for error in validate_eval_item(item))


def test_validate_eval_item_catches_missing_requirements():
    item = sample_eval_item()
    del item["requirements"]

    assert any("requirements" in error for error in validate_eval_item(item))


def test_validate_eval_item_rejects_mixed_requirement():
    item = sample_eval_item()
    item["requirements"][0]["classification_type"] = "MIXED"

    assert any("classification_type" in error for error in validate_eval_item(item))


def test_summarize_generation_result_handles_success_result():
    row = summarize_generation_result(sample_eval_item(), sample_result())

    assert row["backend_status"] == "SUCCESS"
    assert row["schema_pass"] is True
    assert row["success_count"] == 1


def test_summarize_generation_result_counts_test_cases():
    row = summarize_generation_result(sample_eval_item(), sample_result())

    assert row["total_test_cases"] == 1


def test_summarize_generation_result_detects_requirement_id_mismatch():
    row = summarize_generation_result(
        sample_eval_item(),
        sample_result(bundle_requirement_id="REQ_OTHER"),
    )

    assert row["requirement_id_mismatch_count"] == 1


def test_summarize_generation_result_detects_coverage_item_mismatch():
    row = summarize_generation_result(
        sample_eval_item(),
        sample_result(coverage_item="Unplanned coverage item."),
    )

    assert row["coverage_item_mismatch_count"] == 1


def test_summarize_generation_result_detects_rate_limited():
    row = summarize_generation_result(sample_eval_item(), sample_result(status="RATE_LIMITED"))

    assert row["rate_limited"] is True


def test_summarize_generation_result_detects_provider_failed():
    row = summarize_generation_result(sample_eval_item(), sample_result(status="PROVIDER_FAILED"))

    assert row["provider_failed"] is True


def test_aggregate_eval_rows_computes_schema_pass_rate():
    rows = [
        summarize_generation_result(sample_eval_item(), sample_result()),
        summarize_generation_result(sample_eval_item(), {"status": "BROKEN"}),
    ]

    assert aggregate_eval_rows(rows)["schema_pass_rate"] == 0.5


def test_aggregate_eval_rows_computes_average_calls():
    rows = [
        summarize_generation_result(sample_eval_item(), sample_result()),
        summarize_generation_result(sample_eval_item(), sample_result()),
    ]
    rows[1]["calls_used"] = 4

    assert aggregate_eval_rows(rows)["average_calls_used"] == 3


def test_aggregate_eval_rows_computes_average_test_cases_per_requirement():
    rows = [
        summarize_generation_result(sample_eval_item(), sample_result()),
        summarize_generation_result(sample_eval_item(), sample_result()),
    ]

    assert aggregate_eval_rows(rows)["average_test_cases_per_requirement"] == 1


def test_aggregate_eval_rows_quality_gate_passes_when_metrics_are_good():
    row = summarize_generation_result(sample_eval_item(), sample_result())

    gates = aggregate_eval_rows([row])["quality_gates"]

    assert gates["schema_pass_rate_gte_95"] is True
    assert gates["requirement_id_mismatch_zero"] is True
    assert gates["coverage_item_mismatch_zero"] is True


def test_aggregate_eval_rows_quality_gate_fails_when_schema_pass_below_95():
    rows = [
        summarize_generation_result(sample_eval_item(), sample_result()),
        summarize_generation_result(sample_eval_item(), {"status": "BROKEN"}),
    ]

    assert aggregate_eval_rows(rows)["quality_gates"]["schema_pass_rate_gte_95"] is False


def test_write_json_report_creates_file(tmp_path):
    path = tmp_path / "report.json"

    write_json_report(str(path), {"ok": True})

    assert json.loads(path.read_text()) == {"ok": True}


def test_write_csv_rows_creates_file(tmp_path):
    path = tmp_path / "rows.csv"

    write_csv_rows(str(path), [summarize_generation_result(sample_eval_item(), sample_result())])

    assert path.exists()
    assert "eval_id" in path.read_text()


def test_dry_run_cli_validates_dataset_without_calling_test_case_engine(tmp_path):
    reports_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_test_case_evaluation.py",
            "--dry-run",
            "--reports-dir",
            str(reports_dir),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "dataset_valid=True" in completed.stdout
    assert "dry_run=True" in completed.stdout
    assert (reports_dir / "test_case_eval_validation_summary.json").exists()


def test_no_phase12_test_imports_groq_provider():
    text = Path("tests/test_test_case_generation_phase12_evaluation.py").read_text()

    provider_name = "Groq" + "Provider"
    assert provider_name not in text


def test_no_phase12_test_calls_requests_httpx_network():
    text = Path("tests/test_test_case_generation_phase12_evaluation.py").read_text()

    assert "requests" + "." not in text
    assert "httpx" + "." not in text


def test_no_keyword_domain_branching_exists_in_evaluation_py():
    text = Path("app/services/test_case_generation/evaluation.py").read_text()

    forbidden = [
        "requirement" + ".lower(",
        'if "' + "login" + '" in',
        'if "' + "password" + '" in',
        'if "' + "payment" + '" in',
        "keyword-to" + "-test-type maps",
        "keyword-to" + "-technique maps",
        "hardcoded business" + "/domain routing",
    ]

    for fragment in forbidden:
        assert fragment not in text

