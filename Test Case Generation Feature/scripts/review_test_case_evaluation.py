import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.test_case_generation.evaluation import (  # noqa: E402
    aggregate_eval_rows,
    build_manual_review_template,
    merge_manual_review,
    phase12_gate_summary,
    read_csv_rows,
    write_csv_rows,
    write_json_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and aggregate manual review files for Phase 12 evaluation."
    )
    parser.add_argument(
        "--rows",
        default="eval/reports/test_case_eval_rows.csv",
        help="Path to evaluation rows CSV.",
    )
    parser.add_argument(
        "--raw-results",
        default="eval/reports/test_case_eval_raw_results.json",
        help="Path to raw evaluation results JSON.",
    )
    parser.add_argument(
        "--manual-review",
        default="eval/reports/test_case_eval_manual_review.csv",
        help="Path to manual review CSV.",
    )
    parser.add_argument(
        "--reviewed-rows-output",
        default="eval/reports/test_case_eval_rows_reviewed.csv",
        help="Path where reviewed rows CSV is written.",
    )
    parser.add_argument(
        "--final-report-output",
        default="eval/reports/test_case_eval_final_gate_report.json",
        help="Path where final gate report JSON is written.",
    )
    parser.add_argument(
        "--make-template",
        action="store_true",
        help="Create a manual review CSV template.",
    )
    parser.add_argument(
        "--aggregate-reviewed",
        action="store_true",
        help="Aggregate manually reviewed CSV into the final gate report.",
    )
    return parser


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def main() -> int:
    args = parse_args()

    if not args.make_template and not args.aggregate_reviewed:
        build_parser().print_help()
        return 1

    if args.make_template:
        return make_template(args)

    return aggregate_reviewed(args)


def make_template(args: argparse.Namespace) -> int:
    rows = read_csv_rows(args.rows)
    with Path(args.raw_results).open("r", encoding="utf-8") as file:
        raw_results = json.load(file)

    template_rows = build_manual_review_template(raw_results, rows)
    write_csv_rows(args.manual_review, template_rows)
    print(f"manual_review_template={args.manual_review}")
    return 0


def aggregate_reviewed(args: argparse.Namespace) -> int:
    rows = read_csv_rows(args.rows)
    manual_rows = read_csv_rows(args.manual_review)
    reviewed_rows = merge_manual_review(rows, manual_rows)
    aggregate = aggregate_eval_rows(reviewed_rows)
    phase12_gate = phase12_gate_summary(aggregate)
    final_report = {
        "aggregate": aggregate,
        "phase12_gate": phase12_gate,
    }

    write_csv_rows(args.reviewed_rows_output, reviewed_rows)
    write_json_report(args.final_report_output, final_report)
    print(f"reviewed_rows={args.reviewed_rows_output}")
    print(f"final_gate_report={args.final_report_output}")
    print(f"phase12_gate_passed={phase12_gate['phase12_gate_passed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
