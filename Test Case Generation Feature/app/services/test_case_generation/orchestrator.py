import logging
import time

from app.services.test_case_generation.cache import (
    build_cache_key,
    get_cached_result,
    is_cache_enabled,
    store_cached_result,
)
from app.services.test_case_generation.errors import (
    is_rate_limit_error,
    provider_status_from_exception,
)
from app.services.test_case_generation.generator import generate_batch
from app.services.test_case_generation.logging_utils import (
    log_test_case_cache_event,
    log_test_case_chunk,
    log_test_case_request_complete,
    log_test_case_request_start,
    log_test_case_requirement_result,
)
from app.services.test_case_generation.models import (
    GenerationBudget,
    PlannerOutput,
    RequirementReviewResult,
    RequirementForTestCase,
    TestCaseBundle,
    TestCaseGenerationResult,
)
from app.services.test_case_generation.planner import make_blocked_plan, plan_batch
from app.services.test_case_generation.reviewer import review_batch
from app.services.test_case_generation.token_budget import estimate_generation_budget
from app.services.test_case_generation.validation import (
    chunk_requirements,
    make_validation_failed_bundle,
    normalize_requirements,
    validate_bundles_against_source_and_plan,
    validate_mode,
)
from app.shared.llm.exceptions import (
    GroqGovernorLimitExceeded,
    StrictProviderFallbackBlocked,
)
from app.shared.llm.llm_router import (
    configured_provider_name,
    stage_provider_name,
    strict_provider_value,
)
from app.shared.llm.provider_metadata import request_provider_metadata_ctx

logger = logging.getLogger(__name__)

TERMINAL_PROVIDER_STATUSES = {"PROVIDER_FAILED", "RATE_LIMITED"}
USABLE_REVIEW_STATUSES = {"SUCCESS", "NEEDS_REVIEW"}


def _default_provider_metadata() -> dict:
    primary_provider = configured_provider_name()
    if strict_provider_value() and primary_provider == "groq":
        provider_role_map = {"planner": "groq", "generator": "groq", "reviewer": "groq"}
    else:
        provider_role_map = {
            "planner": stage_provider_name("planner", primary_provider),
            "generator": stage_provider_name("generator", primary_provider),
            "reviewer": stage_provider_name("reviewer", primary_provider),
        }
    return {
        "primary_provider": primary_provider,
        "strict_provider": strict_provider_value(),
        "provider_used_by_stage": {},
        "provider_role_map": provider_role_map,
        "fallback_used": False,
        "fallback_provider": None,
        "fallback_reason": None,
        "rate_limit_stage": None,
        "rate_limit_type": None,
        "retry_attempts": 0,
        "provider_wait_seconds_total": 0.0,
        "provider_wait_by_stage": {},
        "provider_wait_by_provider": {},
    }


def _apply_provider_metadata_to_budget(budget: GenerationBudget) -> None:
    metadata = request_provider_metadata_ctx.get() or _default_provider_metadata()
    budget.primary_provider = metadata.get("primary_provider")
    budget.strict_provider = metadata.get("strict_provider")
    budget.provider_used_by_stage = dict(metadata.get("provider_used_by_stage") or {})
    budget.provider_role_map = dict(metadata.get("provider_role_map") or {})
    budget.fallback_used = bool(metadata.get("fallback_used"))
    budget.fallback_provider = metadata.get("fallback_provider")
    budget.fallback_reason = metadata.get("fallback_reason")
    budget.rate_limit_stage = metadata.get("rate_limit_stage")
    budget.rate_limit_type = metadata.get("rate_limit_type")
    budget.retry_attempts = int(metadata.get("retry_attempts") or 0)
    budget.provider_wait_seconds_total = float(
        metadata.get("provider_wait_seconds_total") or 0.0
    )
    budget.provider_wait_by_stage = dict(metadata.get("provider_wait_by_stage") or {})
    budget.provider_wait_by_provider = dict(
        metadata.get("provider_wait_by_provider") or {}
    )


def determine_overall_status(
    results: list[TestCaseBundle],
    warnings: list[str],
) -> str:
    if not results:
        return "FAILED_SCHEMA_VALIDATION"

    statuses = [result.status for result in results]
    usable = [
        result
        for result in results
        if result.status in {"SUCCESS", "NEEDS_REVIEW"} and result.test_cases
    ]

    if all(status == "SUCCESS" for status in statuses):
        return "SUCCESS"
    if any(status == "RATE_LIMITED" for status in statuses):
        return "RATE_LIMITED"
    if any(status == "PROVIDER_FAILED" for status in statuses):
        return "PROVIDER_FAILED"
    if all(status == "BLOCKED_MISSING_INFORMATION" for status in statuses):
        return "BLOCKED_MISSING_INFORMATION"
    if usable and any(
        status in {
            "NEEDS_REVIEW",
            "BLOCKED_MISSING_INFORMATION",
            "FAILED_SCHEMA_VALIDATION",
        }
        for status in statuses
    ):
        return "NEEDS_REVIEW"
    if all(status == "FAILED_SCHEMA_VALIDATION" for status in statuses):
        return "FAILED_SCHEMA_VALIDATION"

    _ = warnings
    return "NEEDS_REVIEW"


def is_terminal_provider_bundle(bundle: TestCaseBundle | None) -> bool:
    return (
        isinstance(bundle, TestCaseBundle)
        and bundle.status in TERMINAL_PROVIDER_STATUSES
    )


def make_blocked_bundle(
    requirement: RequirementForTestCase,
    plan: PlannerOutput | None,
    reason: str | None = None,
) -> TestCaseBundle:
    fallback_reason = reason or "Planner blocked generation"
    plan_warnings = list(plan.blocking_missing_information) if plan else []
    warnings = plan_warnings or [fallback_reason]

    return TestCaseBundle(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        status="BLOCKED_MISSING_INFORMATION",
        test_cases=[],
        missing_information=list(plan.missing_information) if plan else [],
        assumptions=list(plan.assumptions) if plan else [],
        warnings=warnings,
        reason=warnings[0] if warnings else fallback_reason,
    )


def make_provider_failed_bundle(
    requirement: RequirementForTestCase,
    plan: PlannerOutput | None = None,
    reason: str = "Provider failed during test case generation",
) -> TestCaseBundle:
    return TestCaseBundle(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        status="PROVIDER_FAILED",
        test_cases=[],
        missing_information=list(plan.missing_information) if plan else [],
        assumptions=list(plan.assumptions) if plan else [],
        warnings=[reason],
        reason=reason,
    )


def make_provider_error_bundle(
    requirement: RequirementForTestCase,
    plan: PlannerOutput | None,
    exc: Exception,
    stage: str,
) -> TestCaseBundle:
    status = provider_status_from_exception(exc)
    reason = (
        f"{stage} rate-limited during test case generation: {exc}"
        if status == "RATE_LIMITED"
        else f"{stage} failed during test case generation: {exc}"
    )
    return TestCaseBundle(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        status=status,
        test_cases=[],
        missing_information=list(plan.missing_information) if plan else [],
        assumptions=list(plan.assumptions) if plan else [],
        warnings=[reason],
        reason=reason,
    )


def apply_review_results(
    bundles: dict[str, TestCaseBundle],
    review_results: dict[str, RequirementReviewResult],
) -> dict[str, TestCaseBundle]:
    reviewed: dict[str, TestCaseBundle] = {}

    for requirement_id, bundle in bundles.items():
        review_result = review_results.get(requirement_id)
        if review_result is None:
            reviewed[requirement_id] = _mark_bundle_review_needed(
                bundle,
                "Reviewer decision missing",
            )
            continue

        if not review_result.structural_valid:
            reason = "Reviewer output structurally invalid"
            warnings = (
                list(bundle.warnings)
                + list(review_result.warnings)
                + ["Reviewer output structurally invalid; generated cases withheld for human review"]
            )
            reviewed[requirement_id] = TestCaseBundle(
                requirement_id=bundle.requirement_id,
                requirement_text=bundle.requirement_text,
                requirement_type=bundle.requirement_type,
                status="NEEDS_REVIEW",
                test_cases=[],
                missing_information=list(bundle.missing_information),
                assumptions=list(bundle.assumptions),
                warnings=warnings,
                reason=reason,
            )
            continue

        decisions_by_id = {
            decision.test_case_id: decision for decision in review_result.decisions
        }
        kept_cases = []
        warnings = list(bundle.warnings) + list(review_result.warnings)
        needs_review = bundle.status == "NEEDS_REVIEW"

        for test_case in bundle.test_cases:
            decision = decisions_by_id.get(test_case.test_case_id)
            if decision is None:
                needs_review = True
                kept_cases.append(test_case)
                warnings.append(f"{test_case.test_case_id}: Reviewer decision missing")
                continue

            if decision.decision == "KEEP":
                kept_cases.append(test_case)
                continue

            needs_review = True
            warnings.append(f"{test_case.test_case_id}: {decision.reason}")
            if decision.decision == "REVIEW_NEEDED":
                kept_cases.append(test_case)

        if not kept_cases and bundle.test_cases:
            reason = "All generated test cases were rejected by reviewer"
            warnings.append(reason)
            reviewed[requirement_id] = TestCaseBundle(
                requirement_id=bundle.requirement_id,
                requirement_text=bundle.requirement_text,
                requirement_type=bundle.requirement_type,
                status="NEEDS_REVIEW",
                test_cases=[],
                missing_information=list(bundle.missing_information),
                assumptions=list(bundle.assumptions),
                warnings=warnings,
                reason=reason,
            )
            continue

        reviewed[requirement_id] = TestCaseBundle(
            requirement_id=bundle.requirement_id,
            requirement_text=bundle.requirement_text,
            requirement_type=bundle.requirement_type,
            status="NEEDS_REVIEW" if needs_review else bundle.status,
            test_cases=kept_cases,
            missing_information=list(bundle.missing_information),
            assumptions=list(bundle.assumptions),
            warnings=warnings,
            reason=bundle.reason,
        )

    return reviewed


def _mark_bundle_review_needed(bundle: TestCaseBundle, warning: str) -> TestCaseBundle:
    warnings = list(bundle.warnings)
    if warning not in warnings:
        warnings.append(warning)
    return TestCaseBundle(
        requirement_id=bundle.requirement_id,
        requirement_text=bundle.requirement_text,
        requirement_type=bundle.requirement_type,
        status="NEEDS_REVIEW",
        test_cases=list(bundle.test_cases),
        missing_information=list(bundle.missing_information),
        assumptions=list(bundle.assumptions),
        warnings=warnings,
        reason=bundle.reason,
    )
    return TestCaseBundle(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        status=status,
        test_cases=[],
        missing_information=list(plan.missing_information) if plan else [],
        assumptions=list(plan.assumptions) if plan else [],
        warnings=[reason],
        reason=reason,
    )


class TestCaseEngine:
    async def generate(
        self,
        raw_requirements: list[dict],
        project_context: str | None = None,
        mode: str = "mvp_fast",
    ) -> TestCaseGenerationResult:
        start_time = time.time()
        warnings: list[str] = []
        request_provider_metadata_ctx.set(_default_provider_metadata())

        try:
            mode = validate_mode(mode)
            normalized_requirements = normalize_requirements(raw_requirements, mode)
            _, budget, budget_warnings = estimate_generation_budget(
                raw_requirements,
                mode,
            )
            warnings.extend(budget_warnings)
        except Exception as exc:
            return TestCaseGenerationResult(
                status="FAILED_SCHEMA_VALIDATION",
                results=[],
                plans=[],
                warnings=[str(exc)],
                budget=GenerationBudget(
                    mode=mode,
                    estimated_calls=0,
                    estimated_tokens=0,
                    calls_used=0,
                    **_default_provider_metadata(),
                ),
            )

        log_test_case_request_start(
            logger,
            mode=mode,
            requirement_count=len(normalized_requirements),
            estimated_calls=budget.estimated_calls,
            estimated_tokens=budget.estimated_tokens,
        )

        cache_key = None
        try:
            cache_key = build_cache_key(normalized_requirements, project_context, mode)
            cached_result = get_cached_result(cache_key)
            if cached_result is not None:
                cached_result.budget.calls_used = 0
                cached_result.warnings = list(cached_result.warnings)
                if "Served from test case generation cache" not in cached_result.warnings:
                    cached_result.warnings.append("Served from test case generation cache")
                log_test_case_cache_event(
                    logger,
                    "CACHE_HIT",
                    cache_key,
                    mode,
                    len(normalized_requirements),
                )
                log_test_case_request_complete(
                    logger,
                    mode=mode,
                    final_status=cached_result.status,
                    requirement_count=len(normalized_requirements),
                    calls_used=0,
                    estimated_tokens=cached_result.budget.estimated_tokens,
                    cache_hit=True,
                    elapsed_ms=int((time.time() - start_time) * 1000),
                )
                return cached_result

            log_test_case_cache_event(
                logger,
                "CACHE_MISS" if is_cache_enabled() else "CACHE_DISABLED",
                cache_key,
                mode,
                len(normalized_requirements),
            )
        except Exception as exc:
            logger.warning("test case cache lookup failed: %s", exc)

        chunks = chunk_requirements(normalized_requirements, mode)
        results_by_id: dict[str, TestCaseBundle] = {}
        all_plans_by_id: dict[str, PlannerOutput] = {}
        all_plans: list[PlannerOutput] = []
        calls_used = 0

        for chunk_index, chunk in enumerate(chunks, 1):
            try:
                chunk_plans = await plan_batch(chunk, project_context, mode)
                calls_used += 1
            except Exception as exc:
                logger.warning("test case planner chunk failed: %s", exc)
                calls_used += 1
                for requirement in chunk:
                    plan = make_blocked_plan(requirement, "Planner batch failed")
                    all_plans_by_id[requirement.id] = plan
                    all_plans.append(plan)
                    results_by_id[requirement.id] = make_provider_error_bundle(
                        requirement,
                        plan,
                        exc,
                        "Planner",
                    )
                continue

            safe_requirements: list[RequirementForTestCase] = []
            for requirement in chunk:
                plan = chunk_plans.get(requirement.id)
                if plan is None:
                    plan = make_blocked_plan(
                        requirement,
                        "Planner output missing",
                    )

                all_plans_by_id[requirement.id] = plan
                all_plans.append(plan)

                if not plan.safe_to_generate:
                    results_by_id[requirement.id] = make_blocked_bundle(
                        requirement,
                        plan,
                    )
                    continue

                safe_requirements.append(requirement)

            log_test_case_chunk(
                logger,
                mode=mode,
                chunk_index=chunk_index,
                chunk_size=len(chunk),
                safe_count=len(safe_requirements),
                blocked_count=len(chunk) - len(safe_requirements),
            )

            if not safe_requirements:
                continue

            try:
                generated = await generate_batch(
                    safe_requirements,
                    all_plans_by_id,
                    project_context,
                    mode,
                )
                calls_used += 1
            except Exception as exc:
                logger.warning("test case generator chunk failed: %s", exc)
                calls_used += 1
                for requirement in safe_requirements:
                    results_by_id[requirement.id] = make_provider_error_bundle(
                        requirement,
                        all_plans_by_id.get(requirement.id),
                        exc,
                        "Generator",
                    )
                continue

            provider_terminal = {
                requirement_id: bundle
                for requirement_id, bundle in generated.items()
                if is_terminal_provider_bundle(bundle)
            }
            validation_candidates = {
                requirement_id: bundle
                for requirement_id, bundle in generated.items()
                if not is_terminal_provider_bundle(bundle)
            }
            results_by_id.update(provider_terminal)

            candidate_requirements = [
                requirement
                for requirement in safe_requirements
                if requirement.id in validation_candidates
            ]
            if candidate_requirements:
                validated = validate_bundles_against_source_and_plan(
                    validation_candidates,
                    candidate_requirements,
                    all_plans_by_id,
                )
                review_candidates = {
                    requirement_id: bundle
                    for requirement_id, bundle in validated.items()
                    if bundle.status in USABLE_REVIEW_STATUSES and bundle.test_cases
                }
                if review_candidates:
                    review_requirements = [
                        requirement
                        for requirement in candidate_requirements
                        if requirement.id in review_candidates
                    ]
                    try:
                        review_results = await review_batch(
                            review_requirements,
                            all_plans_by_id,
                            review_candidates,
                            project_context,
                            mode,
                        )
                        calls_used += 1
                        validated.update(
                            apply_review_results(review_candidates, review_results)
                        )
                    except Exception as exc:
                        logger.warning("test case reviewer chunk failed: %s", exc)
                        calls_used += 1
                        if isinstance(exc, GroqGovernorLimitExceeded):
                            reviewer_warning = (
                                "Reviewer unavailable because Groq-only provider was "
                                "blocked by governor"
                            )
                        elif is_rate_limit_error(exc):
                            reviewer_warning = (
                                "Reviewer unavailable because Groq-only provider hit "
                                "a rate limit"
                            )
                        elif isinstance(exc, StrictProviderFallbackBlocked):
                            reviewer_warning = (
                                "Reviewer unavailable because Groq-only provider failed"
                            )
                        else:
                            reviewer_warning = (
                                "Reviewer unavailable; generated cases require human review"
                            )
                        for requirement_id, bundle in review_candidates.items():
                            validated[requirement_id] = _mark_bundle_review_needed(
                                bundle,
                                reviewer_warning,
                            )
                results_by_id.update(validated)

        ordered_results = [
            results_by_id.get(requirement.id)
            or make_validation_failed_bundle(
                requirement,
                "Generated result missing",
                all_plans_by_id.get(requirement.id),
            )
            for requirement in normalized_requirements
        ]

        budget.calls_used = calls_used
        _apply_provider_metadata_to_budget(budget)
        final_status = determine_overall_status(ordered_results, warnings)

        for result in ordered_results:
            plan = all_plans_by_id.get(result.requirement_id)
            log_test_case_requirement_result(
                logger,
                requirement_id=result.requirement_id,
                requirement_type=result.requirement_type,
                status=result.status,
                test_case_count=len(result.test_cases),
                risk_level=plan.risk_level if plan else None,
                mode=mode,
            )

        result = TestCaseGenerationResult(
            status=final_status,
            results=ordered_results,
            plans=all_plans,
            warnings=warnings,
            budget=budget,
        )

        try:
            if cache_key:
                store_cached_result(cache_key, result)
                if is_cache_enabled() and result.status not in {"PROVIDER_FAILED", "RATE_LIMITED"}:
                    log_test_case_cache_event(
                        logger,
                        "CACHE_STORE",
                        cache_key,
                        mode,
                        len(normalized_requirements),
                    )
        except Exception as exc:
            logger.warning("test case cache store failed: %s", exc)

        log_test_case_request_complete(
            logger,
            mode=mode,
            final_status=result.status,
            requirement_count=len(normalized_requirements),
            calls_used=result.budget.calls_used,
            estimated_tokens=result.budget.estimated_tokens,
            cache_hit=False,
            elapsed_ms=int((time.time() - start_time) * 1000),
        )
        return result
