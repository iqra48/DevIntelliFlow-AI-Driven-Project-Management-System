import asyncio
import re
from pathlib import Path

from app.services.test_case_generation.models import MODE_CONFIG, RequirementForTestCase
from app.services.test_case_generation.planner import parse_planner_response, plan_batch
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
)
from app.services.test_case_generation.token_budget import estimate_calls, planner_tokens


def requirement(requirement_id: str = "REQ_1") -> RequirementForTestCase:
    return RequirementForTestCase(
        id=requirement_id,
        requirement="The system shall allow users to log in using email and password.",
        classification_type="FR",
    )


def test_prompt_version_unchanged_for_phase15j():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_planner_does_not_retry_malformed_parse_by_default(monkeypatch):
    req = requirement()
    calls = []

    async def fake_call_llm(**kwargs):
        calls.append(kwargs)
        return "not json"

    monkeypatch.setattr("app.services.test_case_generation.planner.call_llm", fake_call_llm)

    result = asyncio.run(plan_batch([req]))

    assert len(calls) == 1
    assert result[req.id].blocking_missing_information == [
        "Planner output could not be parsed. Retry generation."
    ]
    assert result[req.id].planner_parse_attempts == 1


def test_empty_budget_fallback_object_is_internal_formatting_failure():
    req = requirement()

    result = parse_planner_response("{}", [req])
    plan = result[req.id]

    assert plan.safe_to_generate is False
    assert plan.coverage_items == []
    assert plan.blocking_missing_information == [
        "Planner output could not be parsed. Retry generation."
    ]
    assert "Malformed planner response" not in plan.blocking_missing_information


def test_empty_string_is_internal_formatting_failure():
    req = requirement()

    result = parse_planner_response("", [req])

    assert result[req.id].blocking_missing_information == [
        "Planner output could not be parsed. Retry generation."
    ]


def _raw_plan(req: RequirementForTestCase, index: int) -> str:
    return (
        '{"requirement_id":"'
        + req.id
        + '","requirement_text":"'
        + req.requirement
        + '","requirement_type":"FR","testable":true,"safe_to_generate":true,'
        + '"risk_level":"Medium","ambiguity_level":"Low",'
        + '"blocking_missing_information":[],"missing_information":[],'
        + '"coverage_items":[{"coverage_item":"valid configured input succeeds",'
        + '"source_basis":["'
        + req.requirement
        + '"],"test_type":"Positive","technique_used":"Functional verification",'
        + '"priority":"High","rationale":"Covers the stated capability."}],'
        + '"recommended_test_case_count":1,"assumptions":[],'
        + '"why_negative_not_generated":"Negative coverage cannot be generated safely.",'
        + '"why_boundary_not_generated":"Boundary coverage cannot be generated safely."}'
    )


def test_planner_recovers_structural_extra_brace_between_plan_entries():
    reqs = [
        RequirementForTestCase(
            id=f"REQ_{index}",
            requirement=f"The system shall support capability {index}.",
            classification_type="FR",
        )
        for index in range(1, 4)
    ]
    raw = (
        '{"plans":{"1":'
        + _raw_plan(reqs[0], 1)
        + '},"2":'
        + _raw_plan(reqs[1], 2)
        + '},"3":'
        + _raw_plan(reqs[2], 3)
        + "}}"
    )

    result = parse_planner_response(raw, reqs)

    assert set(result) == {"REQ_1", "REQ_2", "REQ_3"}
    assert all(plan.safe_to_generate for plan in result.values())
    assert all(len(plan.coverage_items) == 1 for plan in result.values())


def test_planner_tokens_allow_larger_v12_contract_output():
    requirements = [requirement(f"REQ_{index}") for index in range(1, 6)]

    assert planner_tokens(requirements) > 900
    assert planner_tokens(requirements) <= 5600


def test_call_budget_matches_planner_replan_generator_reviewer_max():
    requirements = [requirement(f"REQ_{index}") for index in range(1, 6)]

    assert estimate_calls(requirements, "mvp_fast") == 4
    assert MODE_CONFIG["mvp_fast"]["max_calls_per_chunk"] == 4
    assert MODE_CONFIG["balanced"]["max_calls_per_chunk"] == 4


def test_no_keyword_domain_branching_added_for_phase15j():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "app/services/test_case_generation/planner.py",
            "app/services/test_case_generation/token_budget.py",
        ]
    )
    keyword_branch = re.compile(
        r"\bif\s+.*(?:login|password|dashboard|otp|button|page|form|api|database).*\s+in\b",
        re.IGNORECASE,
    )

    assert keyword_branch.search(source) is None


def test_no_approved_or_repairer_added_for_phase15j():
    assert not Path("app/services/test_case_generation/repairer.py").exists()
    assert "APPROVED" not in Path("app/services/test_case_generation/models.py").read_text(
        encoding="utf-8"
    )
