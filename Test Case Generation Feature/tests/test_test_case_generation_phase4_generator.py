import asyncio
import json

import pytest

from app.services.test_case_generation.generator import (
    generate_batch,
    parse_generator_response,
)
from app.services.test_case_generation.models import (
    CoverageItem,
    PlannerOutput,
    RequirementForTestCase,
)
from app.services.test_case_generation.prompts import (
    build_generator_system_prompt,
    build_generator_user_prompt,
)
from app.services.test_case_generation.token_budget import generator_tokens
from app.services.test_case_generation.validation import TestCaseValidationError


def requirement(requirement_id="REQ_1", classification_type="FR"):
    return RequirementForTestCase(
        id=requirement_id,
        requirement=f"The system shall process item {requirement_id}.",
        classification_type=classification_type,
    )


def coverage_item(name="Verify stated behavior."):
    return CoverageItem(
        coverage_item=name,
        source_basis=["The system shall process item REQ_1."],
        test_type="Positive",
        technique_used="Functional verification",
        priority="High",
        rationale="Covers the planned behavior.",
    )


def plan(req, safe=True, count=1, missing=None, assumptions=None):
    return PlannerOutput(
        requirement_id=req.id,
        requirement_text=req.requirement,
        requirement_type=req.classification_type,
        testable=safe,
        safe_to_generate=safe,
        risk_level="Medium",
        ambiguity_level="Low",
        blocking_missing_information=[] if safe else ["Needs more detail"],
        missing_information=missing or [],
        coverage_items=[coverage_item()] if safe else [],
        recommended_test_case_count=count if safe else 0,
        assumptions=assumptions or [],
    )


def case_payload(req, case_id=None):
    return {
        "test_case_id": case_id or f"TC_{req.id}_001",
        "requirement_id": req.id,
        "title": "Verify planned behavior",
        "objective": "Confirm the requirement is satisfied.",
        "test_type": "Positive",
        "technique_used": "Functional verification",
        "priority": "High",
        "preconditions": ["System is available."],
        "test_data": {},
        "steps": [
            {
                "step_number": 1,
                "action": "Perform the planned verification.",
                "expected_result": "The requirement outcome is observed.",
            }
        ],
        "expected_result": "The requirement is satisfied.",
        "assumption_required": False,
        "assumptions": [],
        "traceability": {
            "requirement_id": req.id,
            "coverage_item": "Verify stated behavior.",
            "technique_used": "Functional verification",
        },
    }


def bundle_dict(req, test_cases=None, **overrides):
    data = {
        "requirement_id": req.id,
        "requirement_text": req.requirement,
        "requirement_type": req.classification_type,
        "test_cases": test_cases if test_cases is not None else [case_payload(req)],
        "warnings": [],
    }
    data.update(overrides)
    return data


def response_for(*bundles):
    return {"bundles": {str(index): bundle for index, bundle in enumerate(bundles, 1)}}


def assert_failed(bundle, status="FAILED_SCHEMA_VALIDATION"):
    assert bundle.status == status
    assert bundle.test_cases == []
    assert bundle.reason
    assert bundle.warnings


def test_generator_tokens_uses_planned_counts_and_returns_positive_int():
    req = requirement()

    result = generator_tokens([req], [3])

    assert isinstance(result, int)
    assert result > 0


def test_build_generator_system_prompt_says_generator_must_use_planner_coverage():
    prompt = build_generator_system_prompt()

    assert "Generate only for coverage_items supplied by planner" in prompt


def test_build_generator_user_prompt_includes_coverage_item_and_recommended_count():
    req = requirement()
    plans = {req.id: plan(req, count=2)}

    prompt = build_generator_user_prompt([req], plans)

    assert "Verify stated behavior." in prompt
    assert "recommended_test_case_count=2" in prompt


def test_parse_valid_generator_response_for_one_requirement():
    req = requirement()
    plans = {req.id: plan(req)}

    result = parse_generator_response(response_for(bundle_dict(req)), [req], plans)

    assert result[req.id].status == "SUCCESS"
    assert len(result[req.id].test_cases) == 1


def test_parse_valid_generator_response_for_multiple_requirements_in_one_batch():
    reqs = [requirement("REQ_1"), requirement("REQ_2", "NFR")]
    plans = {req.id: plan(req) for req in reqs}

    result = parse_generator_response(
        response_for(bundle_dict(reqs[0]), bundle_dict(reqs[1])),
        reqs,
        plans,
    )

    assert set(result) == {"REQ_1", "REQ_2"}
    assert all(bundle.status == "SUCCESS" for bundle in result.values())


def test_parse_generator_response_recovers_extra_brace_between_bundle_entries():
    reqs = [requirement("REQ_1"), requirement("REQ_2")]
    plans = {req.id: plan(req) for req in reqs}
    first = json.dumps(bundle_dict(reqs[0]), separators=(",", ":"))
    second = json.dumps(bundle_dict(reqs[1]), separators=(",", ":"))
    raw = '{"bundles":{"1":' + first + '},"2":' + second + "}}"

    result = parse_generator_response(raw, reqs, plans)

    assert set(result) == {"REQ_1", "REQ_2"}
    assert all(bundle.status == "SUCCESS" for bundle in result.values())
    assert all(len(bundle.test_cases) == 1 for bundle in result.values())


def test_missing_bundle_index_creates_failed_fallback_only_for_that_requirement():
    reqs = [requirement("REQ_1"), requirement("REQ_2")]
    plans = {req.id: plan(req) for req in reqs}

    result = parse_generator_response(
        {"bundles": {"1": bundle_dict(reqs[0])}},
        reqs,
        plans,
    )

    assert result["REQ_1"].status == "SUCCESS"
    assert_failed(result["REQ_2"])


def test_mismatched_requirement_id_creates_failed_fallback():
    req = requirement()
    plans = {req.id: plan(req)}

    result = parse_generator_response(
        response_for(bundle_dict(req, requirement_id="OTHER")),
        [req],
        plans,
    )

    assert_failed(result[req.id])


def test_mismatched_requirement_text_creates_failed_fallback():
    req = requirement()
    plans = {req.id: plan(req)}

    result = parse_generator_response(
        response_for(bundle_dict(req, requirement_text="Different text.")),
        [req],
        plans,
    )

    assert_failed(result[req.id])


def test_mismatched_requirement_type_creates_failed_fallback():
    req = requirement()
    plans = {req.id: plan(req)}

    result = parse_generator_response(
        response_for(bundle_dict(req, requirement_type="NFR")),
        [req],
        plans,
    )

    assert_failed(result[req.id])


def test_malformed_json_creates_failed_fallback_bundles():
    req = requirement()
    plans = {req.id: plan(req)}

    result = parse_generator_response("not json", [req], plans)

    assert_failed(result[req.id])


def test_malformed_test_case_missing_required_field_causes_bundle_fallback():
    req = requirement()
    plans = {req.id: plan(req)}
    malformed = case_payload(req)
    del malformed["title"]

    result = parse_generator_response(
        response_for(bundle_dict(req, test_cases=[malformed])),
        [req],
        plans,
    )

    assert_failed(result[req.id])


def test_successful_bundle_status_is_needs_review_when_plan_has_missing_information():
    req = requirement()
    plans = {req.id: plan(req, missing=["Clarify external constraint"])}

    result = parse_generator_response(response_for(bundle_dict(req)), [req], plans)

    assert result[req.id].status == "NEEDS_REVIEW"


def test_successful_bundle_status_is_needs_review_when_plan_has_assumptions():
    req = requirement()
    plans = {req.id: plan(req, assumptions=["Standard setup is available"])}

    result = parse_generator_response(response_for(bundle_dict(req)), [req], plans)

    assert result[req.id].status == "NEEDS_REVIEW"


def test_generate_batch_uses_one_llm_call_for_multi_requirement_chunk(monkeypatch):
    reqs = [requirement("REQ_1"), requirement("REQ_2")]
    plans = {req.id: plan(req) for req in reqs}
    calls = []

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        calls.append({"prompt": prompt, "num_predict": num_predict})
        return json.dumps(response_for(bundle_dict(reqs[0]), bundle_dict(reqs[1])))

    monkeypatch.setattr(
        "app.services.test_case_generation.generator.call_llm",
        fake_call_llm,
    )

    result = asyncio.run(generate_batch(reqs, plans))

    assert len(calls) == 1
    assert set(result) == {"REQ_1", "REQ_2"}


def test_generate_batch_does_not_exceed_mode_chunk_size():
    reqs = [requirement(f"REQ_{index}") for index in range(1, 6)]
    plans = {req.id: plan(req) for req in reqs}

    with pytest.raises(TestCaseValidationError):
        asyncio.run(generate_batch(reqs, plans, mode="balanced"))


def test_generate_batch_returns_provider_failed_fallback_when_call_llm_raises(monkeypatch):
    req = requirement()
    plans = {req.id: plan(req)}

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        "app.services.test_case_generation.generator.call_llm",
        fake_call_llm,
    )

    result = asyncio.run(generate_batch([req], plans))

    assert_failed(result[req.id], status="PROVIDER_FAILED")


def test_generate_batch_does_not_call_llm_for_requirement_with_missing_plan(monkeypatch):
    req = requirement()
    calls = []

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        calls.append(prompt)
        return json.dumps({"bundles": {}})

    monkeypatch.setattr(
        "app.services.test_case_generation.generator.call_llm",
        fake_call_llm,
    )

    result = asyncio.run(generate_batch([req], {}))

    assert calls == []
    assert_failed(result[req.id], status="NEEDS_REVIEW")


def test_generate_batch_does_not_call_llm_for_requirement_with_unsafe_plan(monkeypatch):
    req = requirement()
    calls = []
    plans = {req.id: plan(req, safe=False)}

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        calls.append(prompt)
        return json.dumps({"bundles": {}})

    monkeypatch.setattr(
        "app.services.test_case_generation.generator.call_llm",
        fake_call_llm,
    )

    result = asyncio.run(generate_batch([req], plans))

    assert calls == []
    assert_failed(result[req.id], status="NEEDS_REVIEW")


def test_no_planner_call_is_made_from_generator(monkeypatch):
    req = requirement()
    plans = {req.id: plan(req)}

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        return json.dumps(response_for(bundle_dict(req)))

    def fail_plan_batch(*args, **kwargs):
        raise AssertionError("planner should not be called")

    monkeypatch.setattr(
        "app.services.test_case_generation.generator.call_llm",
        fake_call_llm,
    )
    monkeypatch.setattr(
        "app.services.test_case_generation.planner.plan_batch",
        fail_plan_batch,
    )

    result = asyncio.run(generate_batch([req], plans))

    assert result[req.id].status == "SUCCESS"


def test_no_fixed_count_rule_is_enforced_in_generator_parser():
    req = requirement()
    plans = {req.id: plan(req, count=1)}
    cases = [
        case_payload(req, case_id=f"TC_{req.id}_{index:03d}")
        for index in range(1, 5)
    ]

    result = parse_generator_response(
        response_for(bundle_dict(req, test_cases=cases)),
        [req],
        plans,
    )

    assert result[req.id].status == "SUCCESS"
    assert len(result[req.id].test_cases) == 4

