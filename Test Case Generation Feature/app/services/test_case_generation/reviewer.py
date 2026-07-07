import logging
from typing import Any

from app.services.test_case_generation.models import (
    ALLOWED_REVIEW_DECISIONS,
    RequirementForTestCase,
    RequirementReviewResult,
    TestCaseBundle,
    TestCaseReviewDecision,
)
from app.services.test_case_generation.prompts import (
    build_reviewer_system_prompt,
    build_reviewer_user_prompt,
)
from app.services.test_case_generation.token_budget import reviewer_tokens
from app.services.test_case_generation.validation import TestCaseValidationError
from app.shared.llm.call_llm import call_llm
from app.shared.llm.output_guard import parse_json

logger = logging.getLogger(__name__)


def make_review_needed_decision(
    requirement_id,
    test_case_id,
    reason,
) -> TestCaseReviewDecision:
    return TestCaseReviewDecision(
        requirement_id=requirement_id,
        test_case_id=test_case_id,
        decision="REVIEW_NEEDED",
        reason=reason,
        unsupported_elements=[],
        required_human_review=True,
    )


def make_keep_decision(
    requirement_id,
    test_case_id,
    reason="Reviewer unavailable fallback",
) -> TestCaseReviewDecision:
    return TestCaseReviewDecision(
        requirement_id=requirement_id,
        test_case_id=test_case_id,
        decision="KEEP",
        reason=reason,
        unsupported_elements=[],
        required_human_review=False,
    )


def parse_reviewer_response(
    raw,
    requirements: list[RequirementForTestCase],
    bundles: dict[str, TestCaseBundle],
) -> dict[str, RequirementReviewResult]:
    try:
        data = _loads_json(raw)
        reviews = data.get("reviews")
        if not isinstance(reviews, dict):
            raise TestCaseValidationError("reviewer response missing reviews object")
    except Exception as exc:
        logger.warning("reviewer response parse failed: %s", exc)
        return _review_needed_for_all(requirements, bundles, "Malformed reviewer response")

    output: dict[str, RequirementReviewResult] = {}
    for index, requirement in enumerate(requirements, 1):
        bundle = bundles.get(requirement.id)
        if bundle is None:
            continue

        raw_review = reviews.get(str(index))
        if not isinstance(raw_review, dict):
            output[requirement.id] = RequirementReviewResult(
                requirement_id=requirement.id,
                decisions=[
                    make_review_needed_decision(
                        requirement.id,
                        test_case.test_case_id,
                        "Reviewer decision missing",
                    )
                    for test_case in bundle.test_cases
                ],
                warnings=["Reviewer decision missing"],
            )
            continue

        output[requirement.id] = _coerce_requirement_review(
            raw_review,
            requirement,
            bundle,
        )

    return output


async def review_batch(
    requirements: list[RequirementForTestCase],
    plans,
    bundles: dict[str, TestCaseBundle],
    project_context=None,
    mode="mvp_fast",
) -> dict[str, RequirementReviewResult]:
    _ = mode
    prompt = build_reviewer_user_prompt(requirements, plans, bundles, project_context)
    system_prompt = build_reviewer_system_prompt()
    try:
        raw = await call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            num_predict=reviewer_tokens(requirements, bundles),
            stage="reviewer",
        )
    except TypeError as exc:
        if "stage" not in str(exc):
            raise
        raw = await call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            num_predict=reviewer_tokens(requirements, bundles),
        )
    return parse_reviewer_response(raw, requirements, bundles)


def _loads_json(raw) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return parse_json(raw)
    raise TestCaseValidationError("reviewer response must be JSON object text or dict")


def _review_needed_for_all(
    requirements: list[RequirementForTestCase],
    bundles: dict[str, TestCaseBundle],
    reason: str,
) -> dict[str, RequirementReviewResult]:
    output: dict[str, RequirementReviewResult] = {}
    for requirement in requirements:
        bundle = bundles.get(requirement.id)
        if bundle is None:
            continue
        output[requirement.id] = RequirementReviewResult(
            requirement_id=requirement.id,
            decisions=[
                make_review_needed_decision(
                    requirement.id,
                    test_case.test_case_id,
                    reason,
                )
                for test_case in bundle.test_cases
            ],
            warnings=[reason],
        )
    return output


def _coerce_requirement_review(
    raw_review: dict,
    requirement: RequirementForTestCase,
    bundle: TestCaseBundle,
) -> RequirementReviewResult:
    warnings: list[str] = []
    structural_errors: list[str] = []
    if raw_review.get("requirement_id") != requirement.id:
        return RequirementReviewResult(
            requirement_id=requirement.id,
            decisions=[
                make_review_needed_decision(
                    requirement.id,
                    test_case.test_case_id,
                    "Reviewer requirement_id mismatch",
                )
                for test_case in bundle.test_cases
            ],
            warnings=["Reviewer requirement_id mismatch"],
            structural_valid=False,
            structural_errors=["Reviewer requirement_id mismatch"],
        )

    raw_decisions = raw_review.get("decisions")
    if not isinstance(raw_decisions, list):
        raw_decisions = []
        warnings.append("Reviewer decisions missing")

    known_case_ids = {test_case.test_case_id for test_case in bundle.test_cases}
    decisions_by_id: dict[str, TestCaseReviewDecision] = {}

    for raw_decision in raw_decisions:
        try:
            decision = _coerce_decision(raw_decision, requirement.id)
        except Exception:
            test_case_id = (
                raw_decision.get("test_case_id")
                if isinstance(raw_decision, dict)
            else None
            )
            if isinstance(test_case_id, str) and test_case_id in known_case_ids:
                structural_errors.append(f"Invalid reviewer decision: {test_case_id}")
            else:
                structural_errors.append("Invalid reviewer decision")
            continue

        if decision.test_case_id not in known_case_ids:
            structural_errors.append(
                f"Unknown reviewer test_case_id: {decision.test_case_id}"
            )
            continue
        decisions_by_id[decision.test_case_id] = decision

    decisions: list[TestCaseReviewDecision] = []
    for test_case in bundle.test_cases:
        decision = decisions_by_id.get(test_case.test_case_id)
        if decision is None:
            decision = make_review_needed_decision(
                requirement.id,
                test_case.test_case_id,
                "Reviewer decision missing",
            )
        decisions.append(decision)

    review_warnings = raw_review.get("warnings", [])
    if isinstance(review_warnings, list) and all(
        isinstance(item, str) for item in review_warnings
    ):
        warnings.extend(review_warnings)

    if structural_errors:
        warnings.extend(structural_errors)

    return RequirementReviewResult(
        requirement_id=requirement.id,
        decisions=decisions,
        warnings=warnings,
        structural_valid=not structural_errors,
        structural_errors=structural_errors,
    )


def _coerce_decision(raw_decision, requirement_id: str) -> TestCaseReviewDecision:
    if not isinstance(raw_decision, dict):
        raise TestCaseValidationError("review decision must be a dict")
    if raw_decision.get("requirement_id", requirement_id) != requirement_id:
        raise TestCaseValidationError("review decision requirement_id mismatch")

    test_case_id = raw_decision.get("test_case_id")
    if not isinstance(test_case_id, str) or not test_case_id.strip():
        raise TestCaseValidationError("test_case_id must be a non-empty string")

    decision = raw_decision.get("decision")
    if decision not in ALLOWED_REVIEW_DECISIONS:
        raise TestCaseValidationError("review decision enum is invalid")

    reason = raw_decision.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise TestCaseValidationError("reason must be a non-empty string")

    unsupported_elements = raw_decision.get("unsupported_elements")
    if not isinstance(unsupported_elements, list) or not all(
        isinstance(item, str) for item in unsupported_elements
    ):
        raise TestCaseValidationError("unsupported_elements must be list[str]")

    required_human_review = raw_decision.get("required_human_review")
    if not isinstance(required_human_review, bool):
        raise TestCaseValidationError("required_human_review must be bool")

    return TestCaseReviewDecision(
        requirement_id=requirement_id,
        test_case_id=test_case_id,
        decision=decision,
        reason=reason,
        unsupported_elements=unsupported_elements,
        required_human_review=required_human_review,
    )
