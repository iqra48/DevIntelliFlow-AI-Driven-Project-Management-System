import json
import sys
from pathlib import Path

import scripts.merge_test_case_eval_batches as merge_script
import scripts.run_test_case_evaluation as run_script
from app.services.test_case_generation.evaluation import write_csv_rows, write_json_report


def dataset_item(eval_id, category="simple_fr"):
    return {
        "eval_id": eval_id,
        "category": category,
        "mode": "mvp_fast",
        "project_context": None,
        "requirements": [
            {
                "id": "REQ_1",
                "requirement": f"The system shall process {eval_id}.",
                "classification_type": "FR",
            }
        ],
        "expected": {
            "should_generate": True,
            "expected_status_family": "SUCCESS_OR_NEEDS_REVIEW",
        },
    }


def row(eval_id, category="simple_fr", status="SUCCESS"):
    return {
        "eval_id": eval_id,
        "category": category,
        "mode": "mvp_fast",
        "backend_status": status,
        "requirement_count": 1,
        "result_count": 1,
        "plan_count": 1,
        "total_test_cases": 1,
        "calls_used": 3,
        "estimated_calls": 3,
        "estimated_tokens": 1200,
        "schema_pass": True,
        "requirement_id_mismatch_count": 0,
        "coverage_item_mismatch_count": 0,
        "rate_limited": status == "RATE_LIMITED",
        "provider_failed": status == "PROVIDER_FAILED",
        "blocked_count": 0,
        "failed_schema_count": 0,
        "needs_review_count": 0,
        "success_count": 1 if status == "SUCCESS" else 0,
        "manual_unsupported_invention": "",
        "manual_human_edit_needed": "",
        "manual_notes": "",
    }


def raw_result(eval_id, category="simple_fr", status="SUCCESS"):
    return {
        "eval_id": eval_id,
        "category": category,
        "mode": "mvp_fast",
        "result": {
            "status": status,
            "results": [],
            "plans": [],
            "warnings": [],
            "budget": {
                "mode": "mvp_fast",
                "estimated_calls": 3,
                "estimated_tokens": 1200,
                "calls_used": 3,
            },
        },
    }


def write_dataset(path, eval_ids):
    write_json_report(str(path), [dataset_item(eval_id) for eval_id in eval_ids])


def write_batch(
    batches_dir,
    name,
    eval_ids,
    incomplete=False,
    provider="groq",
    strict_provider="true",
    offset=None,
    limit=None,
    statuses=None,
):
    batch_dir = batches_dir / name
    batch_dir.mkdir(parents=True)
    statuses = statuses or {}
    write_csv_rows(
        str(batch_dir / "test_case_eval_rows.csv"),
        [row(eval_id, status=statuses.get(eval_id, "SUCCESS")) for eval_id in eval_ids],
    )
    write_json_report(
        str(batch_dir / "test_case_eval_raw_results.json"),
        [raw_result(eval_id, status=statuses.get(eval_id, "SUCCESS")) for eval_id in eval_ids],
    )
    write_json_report(
        str(batch_dir / "test_case_eval_report.json"),
        {
            "total_eval_items": len(eval_ids),
            "provider": provider,
            "strict_provider": strict_provider,
            "groq_only_evaluation_incomplete": incomplete,
            "offset": offset,
            "limit": limit,
        },
    )
    return batch_dir


def merge(tmp_path, dataset_ids, allow_overwrite=False):
    dataset_path = tmp_path / "dataset.json"
    write_dataset(dataset_path, dataset_ids)
    return merge_script.merge_batches(
        batches_dir=tmp_path / "batches",
        output_dir=tmp_path / "combined",
        dataset_path=dataset_path,
        allow_overwrite=allow_overwrite,
    )


def test_merge_two_batch_dirs_combines_rows(tmp_path):
    batches_dir = tmp_path / "batches"
    write_batch(batches_dir, "offset_0_limit_1", ["EVAL_1"])
    write_batch(batches_dir, "offset_1_limit_1", ["EVAL_2"])

    report = merge(tmp_path, ["EVAL_1", "EVAL_2"])

    assert report["total_merged_eval_items"] == 2
    combined_rows = (tmp_path / "combined" / "combined_rows.csv").read_text()
    assert "EVAL_1" in combined_rows
    assert "EVAL_2" in combined_rows


def test_preserves_dataset_eval_id_order(tmp_path):
    batches_dir = tmp_path / "batches"
    write_batch(batches_dir, "offset_1_limit_1", ["EVAL_B"])
    write_batch(batches_dir, "offset_0_limit_1", ["EVAL_A"])

    merge(tmp_path, ["EVAL_A", "EVAL_B"])
    raw = json.loads((tmp_path / "combined" / "combined_raw_results.json").read_text())

    assert [item["eval_id"] for item in raw] == ["EVAL_A", "EVAL_B"]


def test_detects_missing_eval_ids(tmp_path):
    batches_dir = tmp_path / "batches"
    write_batch(batches_dir, "offset_0_limit_1", ["EVAL_1"])

    report = merge(tmp_path, ["EVAL_1", "EVAL_2"])

    assert report["missing_eval_ids"] == ["EVAL_2"]


def test_detects_duplicate_eval_ids(tmp_path):
    batches_dir = tmp_path / "batches"
    write_batch(batches_dir, "batch_a", ["EVAL_1"])
    write_batch(batches_dir, "batch_b", ["EVAL_1"])

    report = merge(tmp_path, ["EVAL_1"], allow_overwrite=True)

    assert report["duplicate_eval_ids"] == ["EVAL_1"]


def test_duplicate_eval_id_fails_unless_allow_overwrite(tmp_path):
    batches_dir = tmp_path / "batches"
    write_batch(batches_dir, "batch_a", ["EVAL_1"])
    write_batch(batches_dir, "batch_b", ["EVAL_1"])

    try:
        merge(tmp_path, ["EVAL_1"], allow_overwrite=False)
    except ValueError as exc:
        assert "duplicate eval_id" in str(exc)
    else:
        raise AssertionError("duplicate eval_id should fail without allow_overwrite")


def test_detects_incomplete_batch_report(tmp_path):
    batches_dir = tmp_path / "batches"
    incomplete_dir = write_batch(batches_dir, "offset_0_limit_1", ["EVAL_1"], incomplete=True)

    report = merge(tmp_path, ["EVAL_1"])

    assert report["incomplete_batch_dirs"] == [str(incomplete_dir)]


def test_combined_report_incomplete_when_missing_ids_exist(tmp_path):
    batches_dir = tmp_path / "batches"
    write_batch(batches_dir, "offset_0_limit_1", ["EVAL_1"])

    report = merge(tmp_path, ["EVAL_1", "EVAL_2"])

    assert report["groq_only_combined_complete"] is False


def test_combined_report_incomplete_when_any_batch_incomplete(tmp_path):
    batches_dir = tmp_path / "batches"
    write_batch(batches_dir, "offset_0_limit_1", ["EVAL_1"], incomplete=True)

    report = merge(tmp_path, ["EVAL_1"])

    assert report["groq_only_combined_complete"] is False


def test_combined_report_complete_when_all_45_unique_ids_exist(tmp_path):
    eval_ids = [f"EVAL_{index:02d}" for index in range(45)]
    batches_dir = tmp_path / "batches"
    write_batch(batches_dir, "offset_0_limit_20", eval_ids[:20])
    write_batch(batches_dir, "offset_20_limit_20", eval_ids[20:40])
    write_batch(batches_dir, "offset_40_limit_5", eval_ids[40:])

    report = merge(tmp_path, eval_ids)

    assert report["total_expected_eval_items"] == 45
    assert report["total_merged_eval_items"] == 45
    assert report["missing_eval_ids"] == []
    assert report["groq_only_combined_complete"] is True


def test_resume_batches_resolve_historical_incomplete_batch(tmp_path):
    eval_ids = [f"EVAL_{index:02d}" for index in range(5)]
    batches_dir = tmp_path / "batches"
    write_batch(
        batches_dir,
        "offset_0_limit_5",
        eval_ids[:3],
        incomplete=True,
        offset=0,
        limit=5,
    )
    write_batch(batches_dir, "offset_3_limit_2", eval_ids[3:], offset=3, limit=2)

    report = merge(tmp_path, eval_ids)

    assert report["incomplete_batch_dirs"] == []
    assert report["groq_only_combined_complete"] is True


def test_retry_overwrite_resolves_prior_rate_limited_duplicate(tmp_path):
    batches_dir = tmp_path / "batches"
    write_batch(
        batches_dir,
        "offset_0_limit_1",
        ["EVAL_1"],
        incomplete=True,
        offset=0,
        limit=1,
        statuses={"EVAL_1": "RATE_LIMITED"},
    )
    write_batch(
        batches_dir,
        "offset_0_limit_1_retry",
        ["EVAL_1"],
        offset=0,
        limit=1,
    )

    report = merge(tmp_path, ["EVAL_1"], allow_overwrite=True)

    assert report["duplicate_eval_ids"] == []
    assert report["incomplete_batch_dirs"] == []
    assert report["rate_limit_failures"] == 0
    assert report["groq_only_combined_complete"] is True


def test_script_does_not_import_test_case_engine():
    text = Path("scripts/merge_test_case_eval_batches.py").read_text()

    assert "TestCaseEngine" not in text


def test_script_does_not_import_call_llm():
    text = Path("scripts/merge_test_case_eval_batches.py").read_text()

    assert "call_llm" not in text


def test_script_does_not_import_groq_provider():
    text = Path("scripts/merge_test_case_eval_batches.py").read_text()

    assert "GroqProvider" not in text


def test_run_test_case_evaluation_report_includes_offset(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_test_case_evaluation.py",
            "--dry-run",
            "--offset",
            "10",
            "--reports-dir",
            str(tmp_path),
        ],
    )

    assert run_script.main() == 0
    assert "offset=10" in capsys.readouterr().out


def test_run_test_case_evaluation_report_includes_limit(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_test_case_evaluation.py",
            "--dry-run",
            "--limit",
            "5",
            "--reports-dir",
            str(tmp_path),
        ],
    )

    assert run_script.main() == 0
    assert "limit=5" in capsys.readouterr().out


def test_run_test_case_evaluation_live_report_includes_selected_eval_items(
    monkeypatch,
    tmp_path,
):
    async def fake_run_live(items, args):
        return ([row("EVAL_FR_SIMPLE_001")], [raw_result("EVAL_FR_SIMPLE_001")], None)

    monkeypatch.setattr(run_script, "run_live", fake_run_live)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_test_case_evaluation.py",
            "--live",
            "--limit",
            "5",
            "--offset",
            "40",
            "--reports-dir",
            str(tmp_path),
        ],
    )

    assert run_script.main() == 0
    report = json.loads((tmp_path / "test_case_eval_report.json").read_text())
    assert report["offset"] == 40
    assert report["limit"] == 5
    assert report["selected_eval_items"] == 1
