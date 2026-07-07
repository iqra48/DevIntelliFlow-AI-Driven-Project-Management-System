import asyncio
import json

import pytest

from app.services.test_case_generation.models import PlannerOutput, RequirementForTestCase
from app.services.test_case_generation.planner import (
    make_blocked_plan,
    parse_planner_response,
    plan_batch,
)
from app.services.test_case_generation.prompts import build_planner_system_prompt
from app.services.test_case_generation.validation import TestCaseValidationError


def requirement(requirement_id="REQ_1", text=None, classification_type="FR"):
    return RequirementForTestCase(
        id=requirement_id,
        requirement=text or f"The system shall handle request {requirement_id}.",
        classification_type=classification_type,
    )


def coverage_item(test_type="Positive", priority="High"):
    return {
        "coverage_item": "Verify the stated behavior.",
        "source_basis": ["The system shall handle request REQ_1."],
        "test_type": test_type,
        "technique_used": "Functional verification",
        "priority": priority,
        "rationale": "Covers the explicit requirement.",
    }


def plan_dict(req, **overrides):
    data = {
        "requirement_id": req.id,
        "requirement_text": req.requirement,
        "requirement_type": req.classification_type,
        "testable": True,
        "safe_to_generate": True,
        "risk_level": "Medium",
        "ambiguity_level": "Low",
        "blocking_missing_information": [],
        "missing_information": [],
        "coverage_items": [coverage_item()],
        "recommended_test_case_count": 2,
        "assumptions": [],
        "why_negative_not_generated": "Negative coverage cannot be generated safely.",
        "why_boundary_not_generated": "Boundary coverage cannot be generated safely.",
    }
    data.update(overrides)
    return data


def response_for(*plans):
    return {"plans": {str(index): plan for index, plan in enumerate(plans, 1)}}


def assert_blocked(plan):
    assert plan.testable is False
    assert plan.safe_to_generate is False
    assert plan.recommended_test_case_count == 0
    assert plan.coverage_items == []
    assert plan.blocking_missing_information


def test_parse_valid_planner_response_for_one_fr():
    req = requirement(classification_type="FR")

    result = parse_planner_response(response_for(plan_dict(req)), [req])

    assert result[req.id].requirement_id == req.id
    assert result[req.id].safe_to_generate is True


def test_parse_valid_planner_response_for_one_nfr():
    req = requirement(classification_type="NFR")

    result = parse_planner_response(response_for(plan_dict(req)), [req])

    assert result[req.id].requirement_type == "NFR"
    assert result[req.id].coverage_items[0].test_type == "Positive"


def test_parse_valid_planner_response_for_multiple_requirements_in_one_batch():
    reqs = [requirement("REQ_1"), requirement("REQ_2", classification_type="NFR")]

    result = parse_planner_response(
        response_for(plan_dict(reqs[0]), plan_dict(reqs[1])),
        reqs,
    )

    assert set(result) == {"REQ_1", "REQ_2"}
    assert all(plan.safe_to_generate for plan in result.values())


def test_missing_plan_index_creates_blocked_fallback_only_for_that_requirement():
    reqs = [requirement("REQ_1"), requirement("REQ_2")]

    result = parse_planner_response({"plans": {"1": plan_dict(reqs[0])}}, reqs)

    assert result["REQ_1"].safe_to_generate is True
    assert_blocked(result["REQ_2"])


def test_mismatched_requirement_id_creates_blocked_fallback():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, requirement_id="OTHER")),
        [req],
    )

    assert_blocked(result[req.id])


def test_mismatched_requirement_text_creates_blocked_fallback():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, requirement_text="Different text.")),
        [req],
    )

    assert_blocked(result[req.id])


def test_mismatched_requirement_type_creates_blocked_fallback():
    req = requirement(classification_type="FR")

    result = parse_planner_response(
        response_for(plan_dict(req, requirement_type="NFR")),
        [req],
    )

    assert_blocked(result[req.id])


def test_invalid_risk_level_creates_blocked_fallback():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, risk_level="Critical")),
        [req],
    )

    assert_blocked(result[req.id])


def test_invalid_ambiguity_level_creates_blocked_fallback():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, ambiguity_level="Unknown")),
        [req],
    )

    assert_blocked(result[req.id])


def test_invalid_test_type_creates_blocked_fallback():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, coverage_items=[coverage_item(test_type="Other")])),
        [req],
    )

    assert_blocked(result[req.id])


def test_invalid_priority_creates_blocked_fallback():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, coverage_items=[coverage_item(priority="Urgent")])),
        [req],
    )

    assert_blocked(result[req.id])


def test_safe_to_generate_true_with_empty_coverage_items_creates_blocked_fallback():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, coverage_items=[])),
        [req],
    )

    assert_blocked(result[req.id])


def test_safe_to_generate_false_allows_empty_coverage_items_and_count_zero():
    req = requirement()

    result = parse_planner_response(
        response_for(
            plan_dict(
                req,
                testable=False,
                safe_to_generate=False,
                coverage_items=[],
                recommended_test_case_count=0,
                blocking_missing_information=["Missing needed detail"],
            )
        ),
        [req],
    )

    assert result[req.id].safe_to_generate is False
    assert result[req.id].recommended_test_case_count == 0
    assert result[req.id].coverage_items == []


def test_recommended_count_above_mode_max_creates_blocked_fallback():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, recommended_test_case_count=6)),
        [req],
    )

    assert_blocked(result[req.id])


def test_recommended_count_zero_with_safe_to_generate_true_creates_blocked_fallback():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, recommended_test_case_count=0)),
        [req],
    )

    assert_blocked(result[req.id])


def test_plan_batch_uses_one_llm_call_for_multi_requirement_chunk(monkeypatch):
    reqs = [requirement("REQ_1"), requirement("REQ_2")]
    calls = []
    complete_items = [
        coverage_item(test_type="Positive"),
        coverage_item(test_type="Negative"),
        coverage_item(test_type="Boundary"),
    ]

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "num_predict": num_predict,
            }
        )
        return json.dumps(
            response_for(
                plan_dict(reqs[0], coverage_items=complete_items),
                plan_dict(reqs[1], coverage_items=complete_items),
            )
        )

    monkeypatch.setattr(
        "app.services.test_case_generation.planner.call_llm",
        fake_call_llm,
    )

    result = asyncio.run(plan_batch(reqs))

    assert len(calls) == 1
    assert set(result) == {"REQ_1", "REQ_2"}
    assert "Do not generate test cases" in calls[0]["system_prompt"]


def test_plan_batch_does_not_exceed_mode_chunk_size():
    reqs = [requirement(f"REQ_{index}") for index in range(1, 6)]

    with pytest.raises(TestCaseValidationError):
        asyncio.run(plan_batch(reqs, mode="balanced"))


def test_plan_batch_propagates_when_llm_call_raises(monkeypatch):
    reqs = [requirement("REQ_1"), requirement("REQ_2")]

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        "app.services.test_case_generation.planner.call_llm",
        fake_call_llm,
    )

    with pytest.raises(RuntimeError):
        asyncio.run(plan_batch(reqs))


def test_malformed_json_creates_fallback_plans():
    req = requirement()

    result = parse_planner_response("not json", [req])

    assert_blocked(result[req.id])


def test_no_test_case_fields_are_required_or_generated_in_planner_output():
    req = requirement()
    raw_plan = plan_dict(
        req,
        test_cases=[{"title": "Ignored"}],
        steps=[{"action": "Ignored"}],
    )

    result = parse_planner_response(response_for(raw_plan), [req])
    plan = result[req.id]

    assert isinstance(plan, PlannerOutput)
    assert not hasattr(plan, "test_cases")
    assert not hasattr(plan, "steps")
    assert plan.coverage_items


def test_make_blocked_plan_uses_source_requirement_identity():
    req = requirement()

    plan = make_blocked_plan(req, "Blocked")

    assert plan.requirement_id == req.id
    assert plan.requirement_text == req.requirement
    assert plan.requirement_type == req.classification_type


def test_planner_prompt_says_not_to_generate_test_cases():
    assert "Do not generate test cases" in build_planner_system_prompt()

