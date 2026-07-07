import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.services.test_case_generation.evaluation import (  # noqa: E402
    aggregate_eval_rows,
    load_eval_dataset,
    summarize_generation_result,
    validate_eval_dataset,
    write_csv_rows,
    write_json_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the test case generation evaluation dataset."
    )
    parser.add_argument(
        "--dataset",
        default="eval/test_case_generation_eval_dataset.json",
        help="Path to evaluation dataset JSON.",
    )
    parser.add_argument(
        "--reports-dir",
        default="eval/reports",
        help="Directory where evaluation reports are written.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate only.")
    parser.add_argument("--live", action="store_true", help="Run TestCaseEngine.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum eval items to run.")
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Zero-based eval item offset for batched live runs.",
    )
    parser.add_argument(
        "--mode",
        choices=["mvp_fast", "balanced"],
        default=None,
        help="Override mode for every eval item.",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear test case generation cache before running.",
    )
    parser.add_argument(
        "--require-groq-only",
        action="store_true",
        help="Require LLM_PROVIDER=groq and LLM_STRICT_PROVIDER=true for live runs.",
    )
    parser.add_argument(
        "--sleep-between-items",
        type=float,
        default=0.0,
        help="Seconds to sleep between live eval items.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    if args.offset < 0:
        print("offset_invalid=offset must be >= 0")
        return 2
    if args.limit is not None and args.limit < 0:
        print("limit_invalid=limit must be >= 0")
        return 2
    if args.sleep_between_items < 0:
        print("sleep_between_items_invalid=sleep-between-items must be >= 0")
        return 2

    items = load_eval_dataset(args.dataset)
    validation = validate_eval_dataset(items)
    validation_path = reports_dir / "test_case_eval_validation_summary.json"
    write_json_report(str(validation_path), validation)

    print(f"dataset_valid={validation['valid']}")
    print(f"item_count={validation['item_count']}")
    print(f"category_counts={validation['category_counts']}")
    print(f"validation_report={validation_path}")
    print(f"offset={args.offset}")
    print(f"limit={args.limit}")
    print(f"sleep_between_items={args.sleep_between_items}")

    if not validation["valid"]:
        print("Dataset validation failed.")
        return 1

    live = args.live and not args.dry_run
    if not live:
        print("dry_run=True")
        return 0

    provider = os.getenv("LLM_PROVIDER", "").strip().casefold()
    strict_provider = os.getenv("LLM_STRICT_PROVIDER", "false").strip().casefold()
    groq_daily_token_limit = os.getenv("GROQ_DAILY_TOKEN_LIMIT", "100000")
    print(f"provider={provider}")
    print(f"strict_provider={strict_provider}")
    print(f"groq_daily_token_limit={groq_daily_token_limit}")

    if args.require_groq_only:
        if provider != "groq":
            print("require_groq_only_failed=LLM_PROVIDER must be groq")
            return 2
        if strict_provider not in {"true", "1", "yes"}:
            print("require_groq_only_failed=LLM_STRICT_PROVIDER must be true")
            return 2

    print("LIVE evaluation may consume Groq quota.")
    rows, raw_results, incomplete_reason = asyncio.run(run_live(items, args))

    aggregate = aggregate_eval_rows(rows)
    aggregate["offset"] = args.offset
    aggregate["limit"] = args.limit
    aggregate["selected_eval_items"] = len(rows)
    if args.require_groq_only:
        aggregate["provider"] = provider
        aggregate["strict_provider"] = strict_provider
        aggregate["groq_daily_token_limit"] = groq_daily_token_limit
        aggregate["groq_only_evaluation_incomplete"] = incomplete_reason is not None
        aggregate["groq_only_incomplete_reason"] = incomplete_reason
    rows_path = reports_dir / "test_case_eval_rows.csv"
    report_path = reports_dir / "test_case_eval_report.json"
    raw_results_path = reports_dir / "test_case_eval_raw_results.json"

    write_csv_rows(str(rows_path), rows)
    write_json_report(str(report_path), aggregate)
    write_json_report(str(raw_results_path), raw_results)

    print(f"rows_report={rows_path}")
    print(f"aggregate_report={report_path}")
    print(f"raw_results={raw_results_path}")
    print(json.dumps(aggregate, indent=2, ensure_ascii=False))
    return 0


async def run_live(
    items: list[dict],
    args: argparse.Namespace,
) -> tuple[list[dict], list[dict], str | None]:
    from app.services.test_case_generation.cache import clear_test_case_cache
    from app.services.test_case_generation.orchestrator import TestCaseEngine

    if args.clear_cache:
        clear_test_case_cache()

    selected_items = _select_eval_items(items, args.offset, args.limit)
    engine = TestCaseEngine()
    rows: list[dict] = []
    raw_results: list[dict] = []
    incomplete_reason = None

    for item_index, item in enumerate(selected_items):
        if item_index > 0 and args.sleep_between_items:
            await asyncio.sleep(args.sleep_between_items)
        mode = args.mode or item.get("mode", "mvp_fast")
        result = await engine.generate(
            raw_requirements=item["requirements"],
            project_context=item.get("project_context"),
            mode=mode,
        )
        result_dict = result.to_dict()
        eval_item = dict(item)
        eval_item["mode"] = mode
        rows.append(summarize_generation_result(eval_item, result_dict))
        raw_results.append(
            {
                "eval_id": item.get("eval_id"),
                "category": item.get("category"),
                "mode": mode,
                "result": result_dict,
            }
        )
        if args.require_groq_only:
            incomplete_reason = _groq_only_incomplete_reason(result_dict)
        if incomplete_reason is not None:
            print(f"groq_only_evaluation_incomplete={incomplete_reason}")
            break

    return rows, raw_results, incomplete_reason


def _is_local_groq_governor_result(result: dict) -> bool:
    reason = _groq_only_incomplete_reason(result)
    return reason == "Groq-only evaluation incomplete: local Groq governor cap reached"


def _groq_only_incomplete_reason(result: dict) -> str | None:
    messages: list[str] = []
    status = str(result.get("status", ""))
    messages.extend(str(item) for item in result.get("warnings", []))
    for bundle in result.get("results", []):
        if isinstance(bundle, dict):
            messages.extend(str(item) for item in bundle.get("warnings", []))
            messages.append(str(bundle.get("reason", "")))
    text = " ".join(messages).casefold()
    if "governor" in text or "groq local" in text:
        return "Groq-only evaluation incomplete: local Groq governor cap reached"
    if (
        "rate limit" in text
        or "rate-limit" in text
        or "rate-limited" in text
        or "429" in text
        or status == "RATE_LIMITED"
    ):
        return "Groq-only evaluation incomplete: Groq rate limit reached"
    if "groq-only provider failed" in text:
        return "Groq-only evaluation incomplete: Groq provider failed"
    return None


def _select_eval_items(items: list[dict], offset: int, limit: int | None) -> list[dict]:
    if limit is None:
        return items[offset:]
    return items[offset : offset + limit]


if __name__ == "__main__":
    raise SystemExit(main())
