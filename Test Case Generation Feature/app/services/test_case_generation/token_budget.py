from app.services.test_case_generation.models import (
    MODE_CONFIG,
    GenerationBudget,
    RequirementForTestCase,
    TestCaseBundle,
)
from app.services.test_case_generation.validation import (
    TestCaseValidationError,
    chunk_requirements,
    normalize_requirements,
    validate_mode,
)


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def count_words(text: str) -> int:
    """
    Count whitespace-separated words defensively.
    Return 0 for non-string input.
    """
    if not isinstance(text, str):
        return 0

    return len(text.split())


def planner_tokens(requirements: list[RequirementForTestCase]) -> int:
    """
    Estimate output tokens for one planner batch.
    """
    words = sum(count_words(req.requirement) for req in requirements)
    estimated_coverage_items = len(requirements) * 3
    return clamp(900 + estimated_coverage_items * 360 + words * 10, 1200, 5600)


def generator_tokens_preplan(requirements: list[RequirementForTestCase]) -> int:
    """
    Estimate generator output tokens before planner result exists.
    """
    words = sum(count_words(req.requirement) for req in requirements)
    estimated_cases = len(requirements) * 3
    return clamp(900 + estimated_cases * 320 + words * 8, 1200, 5600)


def generator_tokens(
    requirements: list[RequirementForTestCase],
    planned_counts: list[int],
) -> int:
    """
    Estimate generator output tokens after planner result exists.
    """
    words = sum(count_words(req.requirement) for req in requirements)
    cases = sum(planned_counts) if planned_counts else len(requirements) * 3
    return clamp(900 + cases * 320 + words * 8, 1200, 5600)


def reviewer_tokens(
    requirements: list[RequirementForTestCase],
    bundles: dict[str, TestCaseBundle] | list[TestCaseBundle],
) -> int:
    """
    Estimate output tokens for one reviewer batch.
    """
    words = sum(count_words(req.requirement) for req in requirements)
    bundle_values = bundles.values() if isinstance(bundles, dict) else bundles
    test_cases = [
        test_case
        for bundle in bundle_values
        for test_case in getattr(bundle, "test_cases", [])
    ]
    words += sum(
        count_words(test_case.title)
        + count_words(test_case.objective)
        + count_words(test_case.expected_result)
        + sum(count_words(item) for item in test_case.assumptions)
        + sum(
            count_words(step.action) + count_words(step.expected_result)
            for step in test_case.steps
        )
        for test_case in test_cases
    )
    return clamp(500 + len(test_cases) * 90 + words * 4, 500, 1400)


def reviewer_tokens_prebundle(requirements: list[RequirementForTestCase]) -> int:
    estimated_cases = len(requirements) * 2
    words = sum(count_words(req.requirement) for req in requirements)
    return clamp(500 + estimated_cases * 90 + words * 4, 500, 1400)


def estimate_calls(requirements: list[RequirementForTestCase], mode: str) -> int:
    """
    Estimate LLM calls for future planner + optional planner replan + generator + reviewer.
    No actual LLM call.
    """
    chunks = chunk_requirements(requirements, mode)
    return len(chunks) * 4


def estimate_tokens(requirements: list[RequirementForTestCase], mode: str) -> int:
    """
    Estimate total output tokens for all chunks.
    No actual LLM call.
    """
    chunks = chunk_requirements(requirements, mode)
    return sum(
        planner_tokens(chunk)
        + planner_tokens(chunk)
        + generator_tokens_preplan(chunk)
        + reviewer_tokens_prebundle(chunk)
        for chunk in chunks
    )


def estimate_generation_budget(
    raw_requirements: list[dict],
    mode: str = "mvp_fast",
) -> tuple[list[RequirementForTestCase], GenerationBudget, list[str]]:
    """
    Normalize requirements and produce budget estimate.
    """
    normalized_requirements = normalize_requirements(raw_requirements, mode)
    mode = validate_mode(mode)

    budget = GenerationBudget(
        mode=mode,
        estimated_calls=estimate_calls(normalized_requirements, mode),
        estimated_tokens=estimate_tokens(normalized_requirements, mode),
        calls_used=0,
    )

    return normalized_requirements, budget, []


def _mode_limits(mode: str) -> tuple[int | None, int | None]:
    if isinstance(mode, str) and mode in MODE_CONFIG:
        return (
            MODE_CONFIG[mode]["max_requirements"],
            MODE_CONFIG[mode]["chunk_size"],
        )

    return None, None


def estimate_response(raw_requirements: list[dict], mode: str = "mvp_fast") -> dict:
    """
    Return an API-friendly estimate dict.
    """
    max_requirements, chunk_size = _mode_limits(mode)

    try:
        normalized_requirements, budget, warnings = estimate_generation_budget(
            raw_requirements,
            mode,
        )

        return {
            "allowed": True,
            "mode": budget.mode,
            "requirement_count": len(normalized_requirements),
            "estimated_calls": budget.estimated_calls,
            "estimated_tokens": budget.estimated_tokens,
            "max_requirements": MODE_CONFIG[budget.mode]["max_requirements"],
            "chunk_size": MODE_CONFIG[budget.mode]["chunk_size"],
            "warnings": warnings,
        }
    except TestCaseValidationError as exc:
        return {
            "allowed": False,
            "mode": mode,
            "requirement_count": 0,
            "estimated_calls": 0,
            "estimated_tokens": 0,
            "max_requirements": max_requirements,
            "chunk_size": chunk_size,
            "warnings": [str(exc)],
        }
