import logging
import json
import os
import re
import time
import asyncio
from typing import Any

from app.services.test_case_generation.models import (
    MODE_CONFIG,
    CoverageItem,
    PlannerOutput,
    RequirementForTestCase,
)
from app.services.test_case_generation.prompts import (
    PLANNER_AMBIGUITY_OPTIONS,
    PLANNER_PRIORITY_OPTIONS,
    PLANNER_RISK_OPTIONS,
    PLANNER_TECHNIQUE_OPTIONS,
    PLANNER_TEST_TYPE_OPTIONS,
    build_planner_system_prompt,
    build_planner_retry_system_prompt,
    build_planner_replan_system_prompt,
    build_planner_replan_user_prompt,
    build_planner_user_prompt,
)
from app.services.test_case_generation.token_budget import planner_tokens
from app.services.test_case_generation.validation import (
    TestCaseValidationError,
    validate_ambiguity_level,
    validate_mode,
    validate_planner_output_against_requirement,
    validate_priority,
    validate_risk_level,
    validate_test_type,
)
from app.shared.llm.call_llm import call_llm
from app.shared.llm.output_guard import extract_json, parse_json

logger = logging.getLogger(__name__)
INTERNAL_PLANNER_FORMATTING_ERROR = "Internal planner formatting error. Retry generation."


def make_blocked_plan(
    requirement: RequirementForTestCase,
    reason: str,
) -> PlannerOutput:
    """
    Safe fallback when planner cannot safely produce a valid plan.
    """
    return PlannerOutput(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        testable=False,
        safe_to_generate=False,
        risk_level="Medium",
        ambiguity_level="High",
        blocking_missing_information=[reason],
        missing_information=[],
        coverage_items=[],
        recommended_test_case_count=0,
        assumptions=[],
        why_negative_not_generated=None,
        why_boundary_not_generated=None,
        coverage_replan_attempted=False,
        coverage_replan_reason=None,
        coverage_replan_succeeded=None,
    )


def _is_empty_planner_output(raw: Any) -> bool:
    if raw is None:
        return True
    if isinstance(raw, str):
        stripped = raw.strip()
        return stripped in {"", "{}"}
    if isinstance(raw, dict):
        return raw == {}
    return False


def _persist_malformed_planner_raw(raw: Any, label: str = "parse") -> None:
    try:
        os.makedirs("logs", exist_ok=True)
        ts = int(time.time())
        fname = f"logs/planner_malformed_{ts}_{label}.txt"
        with open(fname, "w", encoding="utf-8") as handle:
            if isinstance(raw, (dict, list)):
                handle.write(json.dumps(raw, ensure_ascii=False, indent=2))
            else:
                handle.write(str(raw))
        logger.warning("Persisted malformed planner raw output to %s", fname)
    except Exception as exc:
        logger.warning("Failed to persist malformed planner raw output: %s", exc)


def _parse_repaired_planner_json(raw: str) -> dict[str, Any] | list | None:
    """
    Recover only from structural planner-envelope brace drift.
    This does not create or alter plan content; normal validation still applies.
    """
    try:
        candidate = extract_json(raw)
    except Exception:
        return None

    if '"plans"' not in candidate:
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


def _loads_json(raw: str | dict | list) -> dict[str, Any] | list:
    if isinstance(raw, (dict, list)):
        return raw

    if isinstance(raw, str):
        try:
            return parse_json(raw)
        except Exception:
            recovered = _parse_repaired_planner_json(raw)
            if recovered is not None:
                return recovered
            raise

    raise TestCaseValidationError(
        "planner response must be JSON object/list text, dict, or list"
    )


def _has_plan_fields(value: Any) -> bool:
    """
    Detect a single raw planner object by required structural fields.
    """
    required_fields = {
        "requirement_id",
        "requirement_text",
        "requirement_type",
        "testable",
        "safe_to_generate",
        "coverage_items",
        "recommended_test_case_count",
    }
    return isinstance(value, dict) and required_fields.issubset(value.keys())


def _list_to_indexed_plans(values: list) -> dict[str, Any]:
    return {
        str(index): value
        for index, value in enumerate(values, 1)
    }


def _normalize_plans_container(
    data: dict | list,
    requirements: list[RequirementForTestCase],
) -> dict[str, Any]:
    """
    Accept safe structural variants and normalize to {"1": raw_plan}.
    Structural only. No semantic repair.
    """
    if isinstance(data, list):
        return _list_to_indexed_plans(data)

    if not isinstance(data, dict):
        raise TestCaseValidationError("planner response must be dict or list")

    plans = data.get("plans")
    if isinstance(plans, dict):
        return plans
    if isinstance(plans, list):
        return _list_to_indexed_plans(plans)

    if len(requirements) == 1 and _has_plan_fields(data):
        return {"1": data}

    raise TestCaseValidationError("planner response missing plans object")


def _ensure_list_of_strings(value: Any, field_name: str) -> list[str]:
    # Be tolerant: accept None or boolean False as empty list (some LLM outputs use false)
    if value is None or value is False:
        return []

    if isinstance(value, str):
        value = [value]

    if not isinstance(value, list):
        raise TestCaseValidationError(f"{field_name} must be a list")

    if not all(isinstance(item, str) for item in value):
        raise TestCaseValidationError(f"{field_name} must contain only strings")

    return value


def _ensure_non_empty_list_of_strings(value: Any, field_name: str) -> list[str]:
    strings = [item.strip() for item in _ensure_list_of_strings(value, field_name)]
    strings = [item for item in strings if item]
    if not strings:
        raise TestCaseValidationError(f"{field_name} must be non-empty list[str]")
    return strings


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TestCaseValidationError(f"{field_name} must be string or null")
    return value


def _enum_ref_map(
    options: list[dict],
    ref_field: str,
    value_field: str,
) -> dict[str, str]:
    """
    Return exact ref -> value map.
    """
    return {
        option[ref_field]: option[value_field]
        for option in options
    }


def _enum_value_set(options: list[dict], value_field: str) -> set[str]:
    """
    Return exact allowed values.
    """
    return {
        option[value_field]
        for option in options
    }


def _resolve_enum(
    raw: dict,
    ref_field: str,
    value_field: str,
    options: list[dict],
    field_label: str,
) -> str:
    """
    Resolve enum values by exact structural refs or exact enum values.
    """
    ref_value = raw.get(ref_field)
    if ref_value is not None:
        if not isinstance(ref_value, str):
            raise TestCaseValidationError(f"{field_label} enum ref/value is invalid")

        mapped_value = _enum_ref_map(options, ref_field, value_field).get(ref_value)
        if mapped_value is None:
            raise TestCaseValidationError(f"{field_label} enum ref/value is invalid")

        return mapped_value

    raw_value = raw.get(value_field)
    if not isinstance(raw_value, str):
        raise TestCaseValidationError(f"{field_label} enum ref/value is invalid")

    if raw_value not in _enum_value_set(options, value_field):
        raise TestCaseValidationError(f"{field_label} enum ref/value is invalid")

    return raw_value


def _required_non_empty_string(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise TestCaseValidationError(f"{field_name} must be a non-empty string")

    return value


def _coerce_coverage_item(raw: Any) -> CoverageItem:
    if not isinstance(raw, dict):
        raise TestCaseValidationError("coverage item must be a dict")

    canonical_test_type = _resolve_enum(
        raw,
        "test_type_ref",
        "test_type",
        PLANNER_TEST_TYPE_OPTIONS,
        "test_type",
    )
    canonical_priority = _resolve_enum(
        raw,
        "priority_ref",
        "priority",
        PLANNER_PRIORITY_OPTIONS,
        "priority",
    )
    canonical_technique = _resolve_enum(
        raw,
        "technique_ref",
        "technique_used",
        PLANNER_TECHNIQUE_OPTIONS,
        "technique_used",
    )

    return CoverageItem(
        coverage_item=_required_non_empty_string(raw, "coverage_item"),
        source_basis=_ensure_non_empty_list_of_strings(
            raw.get("source_basis"),
            "source_basis",
        ),
        test_type=validate_test_type(canonical_test_type),
        technique_used=canonical_technique,
        priority=validate_priority(canonical_priority),
        rationale=_required_non_empty_string(raw, "rationale"),
    )


def _coerce_plan(
    raw: Any,
    requirement: RequirementForTestCase,
    mode: str,
) -> PlannerOutput:
    if not isinstance(raw, dict):
        raise TestCaseValidationError("plan must be a dict")

    if not isinstance(raw.get("testable"), bool):
        raise TestCaseValidationError("testable must be bool")
    if not isinstance(raw.get("safe_to_generate"), bool):
        raise TestCaseValidationError("safe_to_generate must be bool")

    canonical_risk = _resolve_enum(
        raw,
        "risk_ref",
        "risk_level",
        PLANNER_RISK_OPTIONS,
        "risk_level",
    )
    canonical_ambiguity = _resolve_enum(
        raw,
        "ambiguity_ref",
        "ambiguity_level",
        PLANNER_AMBIGUITY_OPTIONS,
        "ambiguity_level",
    )

    coverage_items = raw.get("coverage_items")
    if not isinstance(coverage_items, list):
        raise TestCaseValidationError("coverage_items must be a list")

    recommended_count = raw.get("recommended_test_case_count")
    if not isinstance(recommended_count, int):
        raise TestCaseValidationError("recommended_test_case_count must be int")

    plan = PlannerOutput(
        requirement_id=_required_non_empty_string(raw, "requirement_id"),
        requirement_text=_required_non_empty_string(raw, "requirement_text"),
        requirement_type=_required_non_empty_string(raw, "requirement_type"),
        testable=raw["testable"],
        safe_to_generate=raw["safe_to_generate"],
        risk_level=validate_risk_level(canonical_risk),
        ambiguity_level=validate_ambiguity_level(canonical_ambiguity),
        blocking_missing_information=_ensure_list_of_strings(
            raw.get("blocking_missing_information"),
            "blocking_missing_information",
        ),
        missing_information=_ensure_list_of_strings(
            raw.get("missing_information"),
            "missing_information",
        ),
        coverage_items=[_coerce_coverage_item(item) for item in coverage_items],
        recommended_test_case_count=recommended_count,
        assumptions=_ensure_list_of_strings(raw.get("assumptions"), "assumptions"),
        why_negative_not_generated=_optional_string(
            raw.get("why_negative_not_generated"),
            "why_negative_not_generated",
        ),
        why_boundary_not_generated=_optional_string(
            raw.get("why_boundary_not_generated"),
            "why_boundary_not_generated",
        ),
    )

    return validate_planner_output_against_requirement(plan, requirement, mode)


def planner_needs_coverage_replan(plan: PlannerOutput) -> bool:
    """
    Generic structural coverage check for safe FR one-positive plans.
    
    For any safe FR capability plan with only one Positive coverage item,
    trigger semantic replan to attempt expansion to Positive + Negative + Boundary.
    
    Does not inspect requirement text or semantic content; does not check skip reasons.
    Skip reasons (why_negative_not_generated, why_boundary_not_generated) are allowed
    during replan attempts, but alone do not bypass replan triggering.
    """
    if not plan.safe_to_generate:
        return False
    if plan.requirement_type != "FR":
        return False
    if len(plan.coverage_items) != 1:
        return False
    if plan.coverage_items[0].test_type != "Positive":
        return False
    return True


def _add_coverage_expansion_warning(plan: PlannerOutput) -> PlannerOutput:
    """
    Add coverage expansion warning diagnostic to a one-positive safe FR plan
    that failed to expand during replan.
    """
    plan.coverage_replan_succeeded = False
    warning = "Practical coverage expansion did not produce negative and boundary coverage."
    if warning not in plan.missing_information:
        plan.missing_information.append(warning)
    return plan


def _plans_need_coverage_replan(plans: dict[str, PlannerOutput]) -> bool:
    return any(planner_needs_coverage_replan(plan) for plan in plans.values())


def _all_internal_planner_formatting_failures(plans: dict[str, PlannerOutput]) -> bool:
    return bool(plans) and all(
        plan.safe_to_generate is False
        and plan.blocking_missing_information == [INTERNAL_PLANNER_FORMATTING_ERROR]
        for plan in plans.values()
    )


async def _call_planner_llm(prompt: str, system_prompt: str, requirements: list[RequirementForTestCase]) -> Any:
    try:
        return await call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            num_predict=planner_tokens(requirements),
            stage="planner",
        )
    except TypeError as exc:
        if "stage" not in str(exc):
            raise
        return await call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            num_predict=planner_tokens(requirements),
        )


def _indexed_plan_payload(
    requirements: list[RequirementForTestCase],
    plans: dict[str, PlannerOutput],
) -> dict[str, dict]:
    return {
        str(index): plans[requirement.id].to_dict()
        for index, requirement in enumerate(requirements, 1)
        if requirement.id in plans
    }


async def _try_coverage_replan(
    original_plans: dict[str, PlannerOutput],
    requirements: list[RequirementForTestCase],
    project_context: str | None,
    mode: str,
) -> dict[str, PlannerOutput]:
    """
    Attempt semantic replan for safe FR one-positive coverage-incomplete plans.
    Uses dedicated replan system prompt to enforce FR coverage contract.
    """
    replan_system_prompt = build_planner_replan_system_prompt()
    
    prompt = build_planner_replan_user_prompt(
        requirements,
        _indexed_plan_payload(requirements, original_plans),
        project_context,
    )

    output: dict[str, PlannerOutput] = {}

    try:
        raw = await _call_planner_llm(prompt, replan_system_prompt, requirements)
        replanned = parse_planner_response(raw, requirements, mode)
    except Exception as exc:
        logger.warning("planner coverage replan failed: %s", exc)
        # If replan fails, mark the one-positive safe plans with diagnostic
        for requirement in requirements:
            original = original_plans[requirement.id]
            if planner_needs_coverage_replan(original):
                original.coverage_replan_attempted = True
                original.coverage_replan_reason = "Replan LLM call failed"
                original.coverage_replan_succeeded = False
                output[requirement.id] = _add_coverage_expansion_warning(original)
            else:
                output[requirement.id] = original
        return output

    # Process replan results
    for requirement in requirements:
        original = original_plans[requirement.id]
        
        # If original didn't need replan, keep it as-is
        if not planner_needs_coverage_replan(original):
            output[requirement.id] = original
            continue
        
        # Original needed replan; check if replan succeeded
        original.coverage_replan_attempted = True
        original.coverage_replan_reason = "Safe FR with one Positive coverage item"
        
        candidate = replanned.get(requirement.id)
        
        # If replan produced a result that still needs replan, mark as failed
        if candidate is None or planner_needs_coverage_replan(candidate) or not candidate.safe_to_generate:
            original.coverage_replan_succeeded = False
            output[requirement.id] = _add_coverage_expansion_warning(original)
            continue
        
        # Replan succeeded: use the replanned result and mark as such
        candidate.coverage_replan_attempted = True
        candidate.coverage_replan_reason = "Safe FR with one Positive coverage item"
        candidate.coverage_replan_succeeded = True
        output[requirement.id] = candidate

    return output


def parse_planner_response(
    raw: str | dict,
    requirements: list[RequirementForTestCase],
    mode: str = "mvp_fast",
) -> dict[str, PlannerOutput]:
    """
    Parse and validate planner output.
    """
    mode = validate_mode(mode)
    output: dict[str, PlannerOutput] = {}

    if _is_empty_planner_output(raw):
        logger.warning("planner response was empty or budget-fallback object")
        _persist_malformed_planner_raw(raw, "empty")
        return {
            requirement.id: make_blocked_plan(requirement, INTERNAL_PLANNER_FORMATTING_ERROR)
            for requirement in requirements
        }

    try:
        data = _loads_json(raw)
        plans = _normalize_plans_container(data, requirements)
    except Exception as exc:
        logger.warning("planner response parse failed: %s", exc)
        _persist_malformed_planner_raw(raw, "parse")
        return {
            requirement.id: make_blocked_plan(requirement, INTERNAL_PLANNER_FORMATTING_ERROR)
            for requirement in requirements
        }

    for index, requirement in enumerate(requirements, 1):
        raw_plan = plans.get(str(index))
        if raw_plan is None:
            output[requirement.id] = make_blocked_plan(
                requirement,
                "Planner response missing requirement plan",
            )
            continue

        try:
            output[requirement.id] = _coerce_plan(raw_plan, requirement, mode)
        except Exception as exc:
            logger.warning(
                "planner plan invalid requirement_id=%s reason=%s",
                requirement.id,
                exc,
            )
            output[requirement.id] = make_blocked_plan(
                requirement,
                f"Invalid planner output: {exc}",
            )

    return output


async def plan_batch(
    requirements: list[RequirementForTestCase],
    project_context: str | None = None,
    mode: str = "mvp_fast",
) -> dict[str, PlannerOutput]:
    """
    Plan coverage for one chunk of final FR/NFR requirements.
    Returns mapping: requirement_id -> PlannerOutput.
    """
    mode = validate_mode(mode)

    if not requirements:
        raise TestCaseValidationError("requirements must be non-empty")

    chunk_size = MODE_CONFIG[mode]["chunk_size"]
    if len(requirements) > chunk_size:
        raise TestCaseValidationError(
            f"mode {mode} planner chunk size is {chunk_size}"
        )

    prompt = build_planner_user_prompt(requirements, project_context)
    system_prompt = build_planner_system_prompt()

    max_attempts = 3
    last_raw = None
    plans = None

    # Primary call with lightweight retries and retry-system prompt if needed
    for attempt in range(1, max_attempts + 1):
        try:
            raw = await _call_planner_llm(prompt, system_prompt, requirements)
            last_raw = raw
        except Exception as exc:
            logger.warning("planner batch LLM call failed on attempt %d: %s", attempt, exc)
            if attempt == max_attempts:
                raise
            await asyncio.sleep(0.5 * attempt)
            continue

        plans = parse_planner_response(raw, requirements, mode)
        for plan in plans.values():
            plan.planner_parse_attempts = attempt
            plan.planner_raw_response_excerpt = str(raw)[:1000]

        if not _all_internal_planner_formatting_failures(plans):
            return plans

        # If all plans are internal formatting failures, try the retry system prompt once
        if attempt == 1:
            try:
                retry_raw = await _call_planner_llm(
                    prompt,
                    build_planner_retry_system_prompt(),
                    requirements,
                )
                retry_plans = parse_planner_response(retry_raw, requirements, mode)
                for plan in retry_plans.values():
                    plan.planner_parse_attempts = attempt + 1
                    plan.planner_raw_response_excerpt = str(retry_raw)[:1000]
                if not _all_internal_planner_formatting_failures(retry_plans):
                    return retry_plans
                # persist retry raw for debugging
                _persist_malformed_planner_raw(retry_raw, "retry")
            except Exception as exc:
                logger.warning("planner retry-system call failed: %s", exc)

        # persist primary raw for this attempt
        _persist_malformed_planner_raw(raw, f"attempt{attempt}")

        # small backoff before next attempt
        await asyncio.sleep(0.5 * attempt)

    # If we reach here, primary provider couldn't produce valid planner output.
    # Attempt provider-level fallbacks (try other providers in sequence).
    primary = os.getenv("LLM_PROVIDER", "groq").casefold()
    candidates = [p for p in ("groq", "cerebras", "openrouter", "ollama") if p != primary]

    for cand in candidates:
        try:
            old = os.getenv("LLM_PROVIDER")
            os.environ["LLM_PROVIDER"] = cand
            router = LLMRouter()
            try:
                raw = await router.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=None,
                    num_predict=planner_tokens(requirements),
                    stage="planner",
                )
            finally:
                if old is None:
                    os.environ.pop("LLM_PROVIDER", None)
                else:
                    os.environ["LLM_PROVIDER"] = old

            _persist_malformed_planner_raw(raw, f"fallback_{cand}")

            fallback_plans = parse_planner_response(raw, requirements, mode)
            for plan in fallback_plans.values():
                plan.planner_parse_attempts = max(getattr(plan, "planner_parse_attempts", 0), max_attempts)
                plan.planner_raw_response_excerpt = str(raw)[:1000]

            if not _all_internal_planner_formatting_failures(fallback_plans):
                return fallback_plans

        except Exception as exc:
            logger.warning("planner fallback to provider %s failed: %s", cand, exc)
            continue

    # As a last resort, return the last parsed plans (likely internal formatting failures)
    if plans is not None:
        return plans

    raise TestCaseValidationError("planner LLM calls failed")

    plans = parse_planner_response(raw, requirements, mode)
    for plan in plans.values():
        plan.planner_parse_attempts = 1
        plan.planner_raw_response_excerpt = str(raw)[:1000]

    if _all_internal_planner_formatting_failures(plans):
        retry_raw = await _call_planner_llm(
            prompt,
            build_planner_retry_system_prompt(),
            requirements,
        )
        retry_plans = parse_planner_response(retry_raw, requirements, mode)
        for plan in retry_plans.values():
            plan.planner_parse_attempts = 2
            plan.planner_raw_response_excerpt = str(retry_raw)[:1000]
        return retry_plans

    return plans
