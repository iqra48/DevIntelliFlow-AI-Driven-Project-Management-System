import asyncio
import json
import re
from pathlib import Path

from app.services.test_case_generation.models import (
    CoverageItem,
    PlannerOutput,
    RequirementForTestCase,
)
from app.services.test_case_generation.planner import (
    planner_needs_coverage_replan,
    plan_batch,
)
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
    build_planner_system_prompt,
)


def requirement(text: str = "The system shall allow users to log in.") -> RequirementForTestCase:
    return RequirementForTestCase("REQ_1", text, "FR")


def coverage_item(
    req: RequirementForTestCase,
    test_type: str = "Positive",
    coverage_item_text: str | None = None,
) -> dict:
    technique = {
        "Positive": "Functional verification",
        "Negative": "Input validation",
        "Boundary": "Boundary value analysis",
    }[test_type]
    return {
        "coverage_item": coverage_item_text or f"{test_type} generic coverage.",
        "source_basis": [req.requirement],
        "test_type": test_type,
        "technique_used": technique,
        "priority": "High",
        "rationale": "Covers the stated capability generically.",
    }


def plan_dict(
    req: RequirementForTestCase,
    items: list[dict] | None = None,
    safe_to_generate: bool = True,
    why_negative_not_generated: str | None = None,
    why_boundary_not_generated: str | None = None,
) -> dict:
    return {
        "requirement_id": req.id,
        "requirement_text": req.requirement,
        "requirement_type": req.classification_type,
        "testable": safe_to_generate,
        "safe_to_generate": safe_to_generate,
        "risk_level": "Medium",
        "ambiguity_level": "Low",
        "blocking_missing_information": [] if safe_to_generate else ["Missing detail"],
        "missing_information": [],
        "coverage_items": items if safe_to_generate else [],
        "recommended_test_case_count": len(items or []) if safe_to_generate else 0,
        "assumptions": [],
        "why_negative_not_generated": why_negative_not_generated,
        "why_boundary_not_generated": why_boundary_not_generated,
    }


def response_for(plan: dict) -> str:
    return json.dumps({"plans": {"1": plan}})


def planner_output(
    safe_to_generate: bool = True,
    items: list[CoverageItem] | None = None,
    why_negative_not_generated: str | None = None,
    why_boundary_not_generated: str | None = None,
) -> PlannerOutput:
    req = requirement()
    return PlannerOutput(
        requirement_id=req.id,
        requirement_text=req.requirement,
        requirement_type=req.classification_type,
        testable=safe_to_generate,
        safe_to_generate=safe_to_generate,
        risk_level="Medium",
        ambiguity_level="Low",
        blocking_missing_information=[] if safe_to_generate else ["Missing detail"],
        missing_information=[],
        coverage_items=items or [],
        recommended_test_case_count=len(items or []) if safe_to_generate else 0,
        assumptions=[],
        why_negative_not_generated=why_negative_not_generated,
        why_boundary_not_generated=why_boundary_not_generated,
    )


def item(test_type: str) -> CoverageItem:
    return CoverageItem(
        coverage_item=f"{test_type} generic coverage.",
        source_basis=[requirement().requirement],
        test_type=test_type,
        technique_used="Functional verification",
        priority="High",
        rationale="Covers the stated capability generically.",
    )


def prompt() -> str:
    return build_planner_system_prompt().casefold()


def test_planner_prompt_versions_for_phase15h():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_planner_prompt_contains_coverage_contract():
    text = prompt()

    assert "planner coverage contract" in text
    assert "why_negative_not_generated" in text
    assert "why_boundary_not_generated" in text


def test_planner_prompt_example_has_positive_negative_boundary():
    example = prompt().split("output shape", 1)[1]

    assert '"test_type":"positive"' in example
    assert '"test_type":"negative"' in example
    assert '"test_type":"boundary"' in example
    assert '"recommended_test_case_count":3' in example
    assert '"recommended_test_case_count":1' not in example


def test_planner_prompt_keeps_anti_invention_rules():
    text = prompt()

    for phrase in [
        "otp",
        "dashboard",
        "account lockout",
        "exact error message",
        "screen",
        "button",
        "form",
        "api",
        "database",
    ]:
        assert phrase in text


def test_replan_trigger_is_generic_positive_only():
    plan = planner_output(items=[item("Positive")])

    assert planner_needs_coverage_replan(plan) is True


def test_replan_trigger_does_not_activate_for_complete_coverage():
    plan = planner_output(items=[item("Positive"), item("Negative"), item("Boundary")])

    assert planner_needs_coverage_replan(plan) is False


def test_replan_trigger_does_not_activate_for_blocked_plan():
    plan = planner_output(safe_to_generate=False, items=[])

    assert planner_needs_coverage_replan(plan) is False


def test_replan_trigger_still_activates_with_clear_skip_reasons():
    plan = planner_output(
        items=[item("Positive")],
        why_negative_not_generated="Negative coverage cannot be generated safely.",
        why_boundary_not_generated="Boundary coverage cannot be generated safely.",
    )

    assert planner_needs_coverage_replan(plan) is True


def test_mocked_replan_expands_single_positive_to_three_items(monkeypatch):
    req = requirement()
    first = response_for(plan_dict(req, [coverage_item(req, "Positive")]))
    second = response_for(
        plan_dict(
            req,
            [
                coverage_item(req, "Positive", "valid configured input succeeds"),
                coverage_item(req, "Negative", "invalid configured input is rejected"),
                coverage_item(req, "Boundary", "missing required information is handled"),
            ],
        )
    )
    calls = []

    async def fake_call_llm(**kwargs):
        calls.append(kwargs)
        return first if len(calls) == 1 else second

    monkeypatch.setattr("app.services.test_case_generation.planner.call_llm", fake_call_llm)

    result = asyncio.run(plan_batch([req]))
    plan = result[req.id]

    assert len(calls) == 2
    assert [item.test_type for item in plan.coverage_items] == [
        "Positive",
        "Negative",
        "Boundary",
    ]
    assert plan.requirement_id == req.id
    assert plan.requirement_text == req.requirement
    assert plan.requirement_type == req.classification_type


def test_replan_failure_keeps_original_and_adds_safe_missing_information(monkeypatch):
    req = requirement("The system shall allow configured capability.")
    first = response_for(plan_dict(req, [coverage_item(req, "Positive")]))
    calls = []

    async def fake_call_llm(**kwargs):
        calls.append(kwargs)
        return first if len(calls) == 1 else "not json"

    monkeypatch.setattr("app.services.test_case_generation.planner.call_llm", fake_call_llm)

    result = asyncio.run(plan_batch([req]))
    plan = result[req.id]

    assert len(calls) == 2
    assert [item.test_type for item in plan.coverage_items] == ["Positive"]
    assert (
        "Practical coverage expansion did not produce negative and boundary coverage."
        in plan.missing_information
    )


def test_no_approved_or_repairer_contract_added():
    assert "approved" not in prompt()
    assert "repairer" not in prompt()
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_no_keyword_domain_branching_added():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "app/services/test_case_generation/planner.py",
            "app/services/test_case_generation/token_budget.py",
            "app/services/test_case_generation/models.py",
            "app/services/test_case_generation/validation.py",
        ]
    )
    keyword_branch = re.compile(
        r"\bif\s+.*(?:login|password|dashboard|otp|button|page|form|api|database).*\s+in\b",
        re.IGNORECASE,
    )

    assert keyword_branch.search(source) is None
