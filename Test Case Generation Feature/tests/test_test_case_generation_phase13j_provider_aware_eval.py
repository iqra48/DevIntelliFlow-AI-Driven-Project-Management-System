import json
from pathlib import Path

from app.services.test_case_generation.evaluation import (
    aggregate_eval_rows,
    build_manual_review_template,
    summarize_generation_result,
    write_csv_rows,
    write_json_report,
)
from scripts.merge_test_case_eval_batches import merge_batches


def eval_item(eval_id="EVAL_1"):
    return {
        "eval_id": eval_id,
        "category": "simple_fr",
        "mode": "mvp_fast",
        "requirements": [
            {
                "id": "REQ_1",
                "requirement": "The system shall process item.",
                "classification_type": "FR",
            }
        ],
        "expected": {
            "should_generate": True,
            "expected_status_family": "SUCCESS",
        },
    }


def result_with_budget(budget):
    return {
        "status": "SUCCESS",
        "results": [
            {
                "requirement_id": "REQ_1",
                "requirement_text": "The system shall process item.",
                "requirement_type": "FR",
                "status": "SUCCESS",
                "test_cases": [],
                "missing_information": [],
                "assumptions": [],
                "warnings": [],
                "reason": None,
            }
        ],
        "plans": [
            {
                "requirement_id": "REQ_1",
                "requirement_text": "The system shall process item.",
                "requirement_type": "FR",
                "coverage_items": [],
            }
        ],
        "warnings": [],
        "budget": {
            "mode": "mvp_fast",
            "estimated_calls": 3,
            "estimated_tokens": 1000,
            "calls_used": 3,
            **budget,
        },
    }


def provider_budget():
    return {
        "primary_provider": "groq",
        "strict_provider": False,
        "provider_role_map": {
            "planner": "cerebras",
            "generator": "groq",
            "reviewer": "cerebras",
        },
        "provider_used_by_stage": {
            "planner": "cerebras",
            "generator": "groq",
            "reviewer": "cerebras",
        },
        "fallback_used": True,
        "fallback_provider": "cerebras",
        "fallback_reason": "rate limit",
        "rate_limit_stage": "generator",
        "rate_limit_type": "TPM",
        "retry_attempts": 1,
    }


def row_from_budget(budget=None):
    return summarize_generation_result(
        eval_item(),
        result_with_budget(budget or provider_budget()),
    )


def test_summarize_generation_result_extracts_primary_provider():
    assert row_from_budget()["primary_provider"] == "groq"


def test_summarize_generation_result_extracts_strict_provider():
    assert row_from_budget()["strict_provider"] is False


def test_summarize_generation_result_extracts_provider_role_map_json():
    row = row_from_budget()

    assert json.loads(row["provider_role_map_json"])["planner"] == "cerebras"


def test_summarize_generation_result_extracts_provider_used_by_stage_json():
    row = row_from_budget()

    assert json.loads(row["provider_used_by_stage_json"])["generator"] == "groq"


def test_planner_provider_comes_from_provider_used_by_stage_when_present():
    assert row_from_budget()["planner_provider"] == "cerebras"


def test_generator_provider_comes_from_provider_used_by_stage_when_present():
    assert row_from_budget()["generator_provider"] == "groq"


def test_reviewer_provider_comes_from_provider_used_by_stage_when_present():
    assert row_from_budget()["reviewer_provider"] == "cerebras"


def test_missing_provider_used_by_stage_falls_back_to_provider_role_map():
    budget = provider_budget()
    budget["provider_used_by_stage"] = {}

    row = row_from_budget(budget)

    assert row["planner_provider"] == "cerebras"
    assert row["generator_provider"] == "groq"
    assert row["reviewer_provider"] == "cerebras"


def test_missing_provider_role_map_falls_back_to_primary_provider():
    budget = provider_budget()
    budget["provider_used_by_stage"] = {}
    budget["provider_role_map"] = {}
    budget["primary_provider"] = "cerebras"

    row = row_from_budget(budget)

    assert row["planner_provider"] == "cerebras"
    assert row["generator_provider"] == "cerebras"
    assert row["reviewer_provider"] == "cerebras"


def test_provider_signature_is_built_correctly():
    assert (
        row_from_budget()["provider_signature"]
        == "planner=cerebras|generator=groq|reviewer=cerebras"
    )


def test_fallback_used_is_preserved():
    assert row_from_budget()["fallback_used"] is True


def test_fallback_provider_is_preserved():
    assert row_from_budget()["fallback_provider"] == "cerebras"


def test_rate_limit_type_is_preserved():
    assert row_from_budget()["rate_limit_type"] == "TPM"


def test_retry_attempts_is_preserved():
    assert row_from_budget()["retry_attempts"] == 1


def test_aggregate_eval_rows_counts_provider_signatures():
    rows = [row_from_budget(), row_from_budget()]

    report = aggregate_eval_rows(rows)

    assert report["provider_signature_counts"] == {
        "planner=cerebras|generator=groq|reviewer=cerebras": 2
    }


def test_aggregate_eval_rows_counts_stage_providers():
    report = aggregate_eval_rows([row_from_budget()])

    assert report["planner_provider_counts"] == {"cerebras": 1}
    assert report["generator_provider_counts"] == {"groq": 1}
    assert report["reviewer_provider_counts"] == {"cerebras": 1}


def test_aggregate_eval_rows_counts_fallback_used():
    report = aggregate_eval_rows([row_from_budget()])

    assert report["fallback_used_count"] == 1
    assert report["fallback_provider_counts"] == {"cerebras": 1}


def test_manual_review_template_includes_provider_signature():
    row = row_from_budget()
    template = build_manual_review_template(
        [{"eval_id": "EVAL_1", "category": "simple_fr", "result": result_with_budget(provider_budget())}],
        [row],
    )

    assert template[0]["provider_signature"] == row["provider_signature"]
    assert template[0]["planner_provider"] == "cerebras"
    assert template[0]["generator_provider"] == "groq"
    assert template[0]["reviewer_provider"] == "cerebras"
    assert template[0]["fallback_used"] is True
    assert template[0]["fallback_provider"] == "cerebras"


def test_merge_combined_report_includes_provider_signature_counts(tmp_path):
    report = merge_one_batch(tmp_path, [row_from_budget()])

    assert report["provider_signature_counts"] == {
        "planner=cerebras|generator=groq|reviewer=cerebras": 1
    }
    assert report["primary_provider_counts"] == {"groq": 1}
    assert report["fallback_used_count"] == 1


def test_mixed_provider_signatures_add_combined_report_warning(tmp_path):
    row_one = row_from_budget()
    budget_two = provider_budget()
    budget_two["provider_used_by_stage"] = {
        "planner": "cerebras",
        "generator": "cerebras",
        "reviewer": "cerebras",
    }
    row_two = summarize_generation_result(
        eval_item("EVAL_2"),
        result_with_budget(budget_two),
    )
    row_two["eval_id"] = "EVAL_2"

    report = merge_one_batch(tmp_path, [row_one, row_two], eval_ids=["EVAL_1", "EVAL_2"])

    assert "Combined report contains multiple provider signatures" in report["warnings"]


def test_no_prompt_version_changes():
    prompt_text = Path("app/services/test_case_generation/prompts.py").read_text(
        encoding="utf-8"
    )

    assert 'TEST_CASE_GENERATOR_PROMPT_VERSION = "generator_v8"' in prompt_text
    assert 'TEST_CASE_REVIEWER_PROMPT_VERSION = "reviewer_v6"' in prompt_text


def test_no_provider_router_behavior_changes_marker():
    router_text = Path("app/shared/llm/llm_router.py").read_text(encoding="utf-8")

    assert "def _ordered_provider_keys_for_stage" in router_text
    assert "def _generate_with_optional_retry" in router_text


def test_no_repairer_py():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_no_approved_status():
    assert "APPROVED" not in Path("app/services/test_case_generation/models.py").read_text(
        encoding="utf-8"
    )


def merge_one_batch(tmp_path, rows, eval_ids=None):
    eval_ids = eval_ids or ["EVAL_1"]
    dataset_path = tmp_path / "dataset.json"
    dataset = [eval_item(eval_id) for eval_id in eval_ids]
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    batches_dir = tmp_path / "batches"
    batch_dir = batches_dir / "offset_0_limit_1"
    batch_dir.mkdir(parents=True)
    write_csv_rows(str(batch_dir / "test_case_eval_rows.csv"), rows)
    write_json_report(
        str(batch_dir / "test_case_eval_raw_results.json"),
        [
            {
                "eval_id": row["eval_id"],
                "category": row["category"],
                "mode": row["mode"],
                "result": result_with_budget(provider_budget()),
            }
            for row in rows
        ],
    )
    write_json_report(
        str(batch_dir / "test_case_eval_report.json"),
        {
            "offset": 0,
            "limit": len(rows),
            "groq_only_evaluation_incomplete": False,
            "provider": rows[0].get("primary_provider"),
            "strict_provider": str(rows[0].get("strict_provider")),
        },
    )

    return merge_batches(
        batches_dir=batches_dir,
        output_dir=tmp_path / "combined",
        dataset_path=dataset_path,
    )


