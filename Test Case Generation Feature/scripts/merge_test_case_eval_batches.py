import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.test_case_generation.evaluation import (  # noqa: E402
    aggregate_eval_rows,
    load_eval_dataset,
    read_csv_rows,
    write_csv_rows,
    write_json_report,
)


ROWS_FILENAME = "test_case_eval_rows.csv"
REPORT_FILENAME = "test_case_eval_report.json"
RAW_RESULTS_FILENAME = "test_case_eval_raw_results.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge offline Groq-only test case evaluation batch reports."
    )
    parser.add_argument(
        "--batches-dir",
        default="eval/reports/groq_only_batches",
        help="Directory containing per-batch evaluation report subdirectories.",
    )
    parser.add_argument(
        "--output-dir",
        default="eval/reports/groq_only_combined",
        help="Directory where combined reports are written.",
    )
    parser.add_argument(
        "--dataset",
        default="eval/test_case_generation_eval_dataset.json",
        help="Evaluation dataset JSON used for canonical eval_id order.",
    )
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="Allow later batch directories to replace duplicate eval_id rows/results.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = merge_batches(
            batches_dir=Path(args.batches_dir),
            output_dir=Path(args.output_dir),
            dataset_path=Path(args.dataset),
            allow_overwrite=args.allow_overwrite,
        )
    except ValueError as exc:
        print(f"merge_failed={exc}")
        return 2

    print(f"combined_rows={Path(args.output_dir) / 'combined_rows.csv'}")
    print(f"combined_raw_results={Path(args.output_dir) / 'combined_raw_results.json'}")
    print(f"combined_report={Path(args.output_dir) / 'combined_report.json'}")
    print(
        "groq_only_combined_complete="
        f"{report['groq_only_combined_complete']}"
    )
    return 0


def merge_batches(
    batches_dir: Path,
    output_dir: Path,
    dataset_path: Path,
    allow_overwrite: bool = False,
) -> dict:
    expected_eval_ids = _dataset_eval_ids(dataset_path)
    expected_eval_id_set = set(expected_eval_ids)
    batch_dirs = _batch_report_dirs(batches_dir)

    rows_by_eval_id: dict[str, dict] = {}
    raw_by_eval_id: dict[str, dict] = {}
    duplicate_eval_ids: list[str] = []
    incomplete_batch_reports: list[tuple[Path, dict]] = []
    providers: set[str] = set()
    strict_providers: set[str] = set()

    for batch_dir in batch_dirs:
        rows = read_csv_rows(str(batch_dir / ROWS_FILENAME))
        raw_results = _read_json(batch_dir / RAW_RESULTS_FILENAME)
        report = _read_json(batch_dir / REPORT_FILENAME)

        if report.get("groq_only_evaluation_incomplete") is True:
            incomplete_batch_reports.append((batch_dir, report))

        if report.get("provider"):
            providers.add(str(report["provider"]))
        if report.get("strict_provider"):
            strict_providers.add(str(report["strict_provider"]))

        for row in rows:
            eval_id = row.get("eval_id")
            if not eval_id:
                continue
            if eval_id in rows_by_eval_id:
                if not _is_resolved_retry(rows_by_eval_id[eval_id], row):
                    duplicate_eval_ids.append(eval_id)
                if not allow_overwrite:
                    continue
            rows_by_eval_id[eval_id] = row

        for raw_result in raw_results:
            if not isinstance(raw_result, dict):
                continue
            eval_id = raw_result.get("eval_id")
            if not eval_id:
                continue
            if eval_id in raw_by_eval_id:
                if not allow_overwrite:
                    continue
            raw_by_eval_id[eval_id] = raw_result

    if duplicate_eval_ids and not allow_overwrite:
        raise ValueError(
            "duplicate eval_id found; rerun with --allow-overwrite to merge: "
            + ", ".join(sorted(set(duplicate_eval_ids)))
        )

    ordered_rows = [
        rows_by_eval_id[eval_id]
        for eval_id in expected_eval_ids
        if eval_id in rows_by_eval_id
    ]
    ordered_raw_results = [
        raw_by_eval_id[eval_id]
        for eval_id in expected_eval_ids
        if eval_id in raw_by_eval_id
    ]
    missing_eval_ids = [
        eval_id
        for eval_id in expected_eval_ids
        if eval_id not in rows_by_eval_id or eval_id not in raw_by_eval_id
    ]
    extra_eval_ids = sorted(
        {
            *rows_by_eval_id.keys(),
            *raw_by_eval_id.keys(),
        }
        - expected_eval_id_set
    )

    aggregate = aggregate_eval_rows(ordered_rows)
    incomplete_batch_dirs = _unresolved_incomplete_batch_dirs(
        incomplete_batch_reports,
        expected_eval_ids,
        rows_by_eval_id,
        raw_by_eval_id,
    )
    provider = _single_or_mixed(providers)
    strict_provider = _single_or_mixed(strict_providers)
    warnings = []
    if len(aggregate.get("provider_signature_counts", {})) > 1:
        warnings.append("Combined report contains multiple provider signatures")
    combined_report = {
        **aggregate,
        "total_expected_eval_items": len(expected_eval_ids),
        "total_merged_eval_items": len(ordered_rows),
        "missing_eval_ids": missing_eval_ids,
        "duplicate_eval_ids": sorted(set(duplicate_eval_ids)),
        "extra_eval_ids": extra_eval_ids,
        "incomplete_batch_dirs": incomplete_batch_dirs,
        "provider": provider,
        "strict_provider": strict_provider,
        "warnings": warnings,
        "groq_only_combined_complete": (
            len(ordered_rows) == len(expected_eval_ids)
            and not missing_eval_ids
            and not incomplete_batch_dirs
            and not extra_eval_ids
            and aggregate.get("rate_limit_failures") == 0
            and aggregate.get("provider_failures") == 0
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv_rows(str(output_dir / "combined_rows.csv"), ordered_rows)
    write_json_report(str(output_dir / "combined_raw_results.json"), ordered_raw_results)
    write_json_report(str(output_dir / "combined_report.json"), combined_report)
    return combined_report


def _dataset_eval_ids(dataset_path: Path) -> list[str]:
    items = load_eval_dataset(str(dataset_path))
    eval_ids = [
        item.get("eval_id")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("eval_id"), str)
    ]
    if len(eval_ids) != len(items):
        raise ValueError("dataset contains item without eval_id")
    return eval_ids


def _batch_report_dirs(batches_dir: Path) -> list[Path]:
    if not batches_dir.exists():
        return []
    return sorted(
        path
        for path in batches_dir.iterdir()
        if path.is_dir()
        and (path / ROWS_FILENAME).exists()
        and (path / RAW_RESULTS_FILENAME).exists()
        and (path / REPORT_FILENAME).exists()
    )


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _unresolved_incomplete_batch_dirs(
    incomplete_batch_reports: list[tuple[Path, dict]],
    expected_eval_ids: list[str],
    rows_by_eval_id: dict[str, dict],
    raw_by_eval_id: dict[str, dict],
) -> list[str]:
    unresolved: list[str] = []
    for batch_dir, report in incomplete_batch_reports:
        intended_eval_ids = _intended_eval_ids(report, expected_eval_ids)
        if not intended_eval_ids:
            unresolved.append(str(batch_dir))
            continue
        if any(
            eval_id not in rows_by_eval_id
            or eval_id not in raw_by_eval_id
            or _row_has_provider_terminal_status(rows_by_eval_id[eval_id])
            for eval_id in intended_eval_ids
        ):
            unresolved.append(str(batch_dir))
    return unresolved


def _intended_eval_ids(report: dict, expected_eval_ids: list[str]) -> list[str]:
    offset = report.get("offset")
    limit = report.get("limit")
    if not isinstance(offset, int):
        return []
    if limit is None:
        return expected_eval_ids[offset:]
    if not isinstance(limit, int):
        return []
    return expected_eval_ids[offset : offset + limit]


def _is_resolved_retry(existing_row: dict, new_row: dict) -> bool:
    return _row_has_provider_terminal_status(existing_row) and not _row_has_provider_terminal_status(new_row)


def _row_has_provider_terminal_status(row: dict) -> bool:
    return (
        str(row.get("backend_status", "")).strip() in {"RATE_LIMITED", "PROVIDER_FAILED"}
        or str(row.get("rate_limited", "")).strip().casefold() in {"true", "1", "yes"}
        or str(row.get("provider_failed", "")).strip().casefold() in {"true", "1", "yes"}
    )


def _single_or_mixed(values: set[str]) -> str | None:
    if not values:
        return None
    if len(values) == 1:
        return next(iter(values))
    return "mixed"


if __name__ == "__main__":
    raise SystemExit(main())
