import logging
import json
import os
import re
import time
from typing import Any

from app.services.test_case_generation.models import (
    CoverageItem,
    MODE_CONFIG,
    PlannerOutput,
    RequirementForTestCase,
    TestCase,
    TestCaseBundle,
    TestStep,
)
from app.services.test_case_generation.errors import provider_status_from_exception
from app.services.test_case_generation.prompts import (
    build_generator_system_prompt,
    build_generator_user_prompt,
)
from app.services.test_case_generation.token_budget import generator_tokens
from app.services.test_case_generation.validation import (
    TestCaseValidationError,
    validate_mode,
    validate_status,
)
from app.shared.llm.call_llm import call_llm
from app.shared.llm.output_guard import extract_json, parse_json

logger = logging.getLogger(__name__)


def make_failed_bundle(
    requirement: RequirementForTestCase,
    status: str,
    reason: str,
    plan: PlannerOutput | None = None,
) -> TestCaseBundle:
    """
    Create fallback TestCaseBundle with empty test_cases.
    """
    status = validate_status(status)
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


def _persist_malformed_generator_raw(raw: Any, label: str = "parse") -> None:
    try:
        os.makedirs("logs", exist_ok=True)
        ts = int(time.time())
        fname = f"logs/generator_malformed_{ts}_{label}.txt"
        with open(fname, "w", encoding="utf-8") as handle:
            if isinstance(raw, (dict, list)):
                handle.write(json.dumps(raw, ensure_ascii=False, indent=2))
            else:
                handle.write(str(raw))
        logger.warning("Persisted malformed generator raw output to %s", fname)
    except Exception as exc:
        logger.warning("Failed to persist malformed generator raw output: %s", exc)


def _parse_repaired_generator_json(raw: str) -> dict[str, Any] | None:
    """
    Recover only from structural generator-envelope brace drift.
    This does not create or alter test cases; normal validation still applies.
    """
    try:
        candidate = extract_json(raw)
    except Exception:
        return None

    if '"bundles"' not in candidate:
        return None

    candidate = re.sub(
        r"}}(\s*,\s*\"\d+\"\s*:\s*\{)",
        r"}\1",
        candidate,
    )

    for _ in range(4):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            trailing = candidate[exc.pos:].strip()
            if exc.msg == "Extra data" and trailing and set(trailing) == {"}"}:
                candidate = candidate[: exc.pos] + trailing[1:]
                continue
            return None

    return None


def _loads_json(raw: str | dict) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str):
        try:
            return parse_json(raw)
        except Exception:
            recovered = _parse_repaired_generator_json(raw)
            if recovered is not None:
                return recovered
            raise

    raise TestCaseValidationError("generator response must be JSON object text or dict")


def _ensure_list_of_strings(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise TestCaseValidationError(f"{field_name} must be a list")

    if not all(isinstance(item, str) for item in value):
        raise TestCaseValidationError(f"{field_name} must contain only strings")

    return value


def _coerce_step(raw: Any) -> TestStep:
    if not isinstance(raw, dict):
        raise TestCaseValidationError("step must be a dict")

    return TestStep(
        step_number=raw["step_number"],
        action=raw["action"],
        expected_result=raw["expected_result"],
    )


def _coverage_ref_map(plan: PlannerOutput) -> dict[str, CoverageItem]:
    return {
        f"COV_{index}": item
        for index, item in enumerate(plan.coverage_items, 1)
    }


def _coverage_item_exact_map(plan: PlannerOutput) -> dict[str, CoverageItem]:
    return {
        item.coverage_item: item
        for item in plan.coverage_items
    }


def _resolve_planned_coverage(raw_test_case: dict, plan: PlannerOutput) -> CoverageItem:
    """
    Resolve planner coverage by exact structural identifiers only.
    """
    traceability = raw_test_case.get("traceability")
    if not isinstance(traceability, dict):
        raise TestCaseValidationError("traceability must be a dict")

    coverage_ref = traceability.get("coverage_ref")
    if coverage_ref is not None:
        if not isinstance(coverage_ref, str):
            raise TestCaseValidationError("coverage_ref must be a string")
        planned_item = _coverage_ref_map(plan).get(coverage_ref)
        if planned_item is not None:
            return planned_item
        raise TestCaseValidationError(
            "coverage_ref or coverage_item does not match planner coverage"
        )

    coverage_item = traceability.get("coverage_item")
    if isinstance(coverage_item, str):
        planned_item = _coverage_item_exact_map(plan).get(coverage_item)
        if planned_item is not None:
            return planned_item

    raise TestCaseValidationError(
        "coverage_ref or coverage_item does not match planner coverage"
    )


def _coerce_test_case(raw: Any, plan: PlannerOutput) -> TestCase:
    if not isinstance(raw, dict):
        raise TestCaseValidationError("test case must be a dict")

    planned_item = _resolve_planned_coverage(raw, plan)
    source_basis = list(planned_item.source_basis)
    steps = raw["steps"]
    if not isinstance(steps, list):
        raise TestCaseValidationError("steps must be a list")

    traceability = {
        "requirement_id": raw["requirement_id"],
        "coverage_item": planned_item.coverage_item,
        "technique_used": planned_item.technique_used,
    }

    return TestCase(
        test_case_id=raw["test_case_id"],
        requirement_id=raw["requirement_id"],
        title=raw["title"],
        objective=raw["objective"],
        test_type=planned_item.test_type,
        technique_used=planned_item.technique_used,
        priority=planned_item.priority,
        preconditions=_ensure_list_of_strings(raw["preconditions"], "preconditions"),
        test_data=raw["test_data"],
        steps=[_coerce_step(step) for step in steps],
        expected_result=raw["expected_result"],
        assumption_required=raw["assumption_required"],
        assumptions=_ensure_list_of_strings(raw["assumptions"], "assumptions"),
        source_basis=source_basis,
        traceability=traceability,
    )


def _coerce_bundle(
    raw: Any,
    requirement: RequirementForTestCase,
    plan: PlannerOutput,
) -> TestCaseBundle:
    if not isinstance(raw, dict):
        raise TestCaseValidationError("bundle must be a dict")

    if raw.get("requirement_id") != requirement.id:
        raise TestCaseValidationError("requirement_id does not match source")
    if raw.get("requirement_text") != requirement.requirement:
        raise TestCaseValidationError("requirement_text does not match source")
    if raw.get("requirement_type") != requirement.classification_type:
        raise TestCaseValidationError("requirement_type does not match source")

    test_cases = raw.get("test_cases")
    if not isinstance(test_cases, list):
        raise TestCaseValidationError("test_cases must be a list")

    warnings = _ensure_list_of_strings(raw.get("warnings", []), "warnings")
    status = "NEEDS_REVIEW" if plan.missing_information or plan.assumptions else "SUCCESS"

    return TestCaseBundle(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        status=status,
        test_cases=[_coerce_test_case(item, plan) for item in test_cases],
        missing_information=list(plan.missing_information),
        assumptions=list(plan.assumptions),
        warnings=warnings,
        reason=None,
    )


def parse_generator_response(
    raw: str | dict,
    requirements: list[RequirementForTestCase],
    plans: dict[str, PlannerOutput],
    mode: str = "mvp_fast",
) -> dict[str, TestCaseBundle]:
    """
    Parse generator output into TestCaseBundle objects.
    Basic structural parsing only.
    """
    validate_mode(mode)

    try:
        data = _loads_json(raw)
        bundles = data.get("bundles")
        if not isinstance(bundles, dict):
            raise TestCaseValidationError("generator response missing bundles object")
    except Exception as exc:
        logger.warning("generator response parse failed: %s", exc)
        _persist_malformed_generator_raw(raw, "parse")
        return {
            requirement.id: make_failed_bundle(
                requirement,
                "FAILED_SCHEMA_VALIDATION",
                "Malformed generator response",
                plans.get(requirement.id),
            )
            for requirement in requirements
        }

    output: dict[str, TestCaseBundle] = {}
    for index, requirement in enumerate(requirements, 1):
        plan = plans.get(requirement.id)
        raw_bundle = bundles.get(str(index))

        if raw_bundle is None:
            output[requirement.id] = make_failed_bundle(
                requirement,
                "FAILED_SCHEMA_VALIDATION",
                "Generator response missing requirement bundle",
                plan,
            )
            continue

        try:
            output[requirement.id] = _coerce_bundle(raw_bundle, requirement, plan)
        except Exception as exc:
            logger.warning(
                "generator bundle invalid requirement_id=%s reason=%s",
                requirement.id,
                exc,
            )
            output[requirement.id] = make_failed_bundle(
                requirement,
                "FAILED_SCHEMA_VALIDATION",
                f"Invalid generator output: {exc}",
                plan,
            )

    return output


async def generate_batch(
    requirements: list[RequirementForTestCase],
    plans: dict[str, PlannerOutput],
    project_context: str | None = None,
    mode: str = "mvp_fast",
) -> dict[str, TestCaseBundle]:
    """
    Generate test cases for one chunk of safe final FR/NFR requirements.
    Returns mapping: requirement_id -> TestCaseBundle.
    """
    mode = validate_mode(mode)

    if not requirements:
        raise TestCaseValidationError("requirements must be non-empty")

    chunk_size = MODE_CONFIG[mode]["chunk_size"]
    if len(requirements) > chunk_size:
        raise TestCaseValidationError(
            f"mode {mode} generator chunk size is {chunk_size}"
        )

    output: dict[str, TestCaseBundle] = {}
    safe_requirements: list[RequirementForTestCase] = []

    for requirement in requirements:
        plan = plans.get(requirement.id)
        if not plan or not plan.safe_to_generate:
            output[requirement.id] = make_failed_bundle(
                requirement,
                "NEEDS_REVIEW",
                "Requirement has no safe planner output",
                plan,
            )
            continue

        safe_requirements.append(requirement)

    if not safe_requirements:
        return output

    planned_counts = [
        plans[requirement.id].recommended_test_case_count
        for requirement in safe_requirements
    ]
    prompt = build_generator_user_prompt(
        safe_requirements,
        plans,
        project_context,
    )
    system_prompt = build_generator_system_prompt()

    try:
        try:
            raw = await call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                num_predict=generator_tokens(safe_requirements, planned_counts),
                stage="generator",
            )
        except TypeError as exc:
            if "stage" not in str(exc):
                raise
            raw = await call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                num_predict=generator_tokens(safe_requirements, planned_counts),
            )
        output.update(parse_generator_response(raw, safe_requirements, plans, mode))
    except Exception as exc:
        logger.warning("generator batch failed: %s", exc)
        status = provider_status_from_exception(exc)
        reason = (
            f"Generator LLM call rate-limited: {exc}"
            if status == "RATE_LIMITED"
            else f"Generator LLM call failed: {exc}"
        )
        for requirement in safe_requirements:
            output[requirement.id] = make_failed_bundle(
                requirement,
                status,
                reason,
                plans.get(requirement.id),
            )

    return output
