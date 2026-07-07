import asyncio
from pathlib import Path

import pytest

from app.services.test_case_generation.cache import clear_test_case_cache
from app.services.test_case_generation.models import (
    CoverageItem,
    PlannerOutput,
    RequirementReviewResult,
    RequirementForTestCase,
    TestCase as CaseModel,
    TestCaseBundle as BundleModel,
    TestCaseReviewDecision as ReviewDecisionModel,
    TestStep as StepModel,
)
from app.services.test_case_generation.orchestrator import (
    TestCaseEngine,
    determine_overall_status,
)


@pytest.fixture(autouse=True)
def clear_cache_between_tests(monkeypatch):
    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        return {
            requirement.id: RequirementReviewResult(
                requirement_id=requirement.id,
                decisions=[
                    ReviewDecisionModel(
                        requirement_id=requirement.id,
                        test_case_id=test_case.test_case_id,
                        decision="KEEP",
                        reason="Kept by test reviewer.",
                        unsupported_elements=[],
                        required_human_review=False,
                    )
                    for test_case in bundles[requirement.id].test_cases
                ],
                warnings=[],
            )
            for requirement in requirements
            if requirement.id in bundles
        }

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)
    clear_test_case_cache()
    yield
    clear_test_case_cache()


def raw_requirement(requirement_id="REQ_1", classification_type="FR"):
    return {
        "id": requirement_id,
        "requirement": f"The system shall process record {requirement_id}.",
        "classification_type": classification_type,
    }


def requirement_from_raw(raw):
    return RequirementForTestCase(
        id=raw["id"],
        requirement=raw["requirement"],
        classification_type=raw["classification_type"],
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


def plan_for(requirement, safe=True, count=1):
    return PlannerOutput(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        testable=safe,
        safe_to_generate=safe,
        risk_level="Medium",
        ambiguity_level="Low" if safe else "High",
        blocking_missing_information=[] if safe else ["Missing required detail"],
        missing_information=[],
        coverage_items=[coverage_item()] if safe else [],
        recommended_test_case_count=count if safe else 0,
        assumptions=[],
    )


def case_for(requirement, case_id=None):
    item = coverage_item()
    return CaseModel(
        test_case_id=case_id or f"TC_{requirement.id}_001",
        requirement_id=requirement.id,
        title="Verify planned behavior",
        objective="Confirm the requirement is satisfied.",
        test_type=item.test_type,
        technique_used=item.technique_used,
        priority=item.priority,
        preconditions=["System is available."],
        test_data={},
        steps=[
            StepModel(
                step_number=1,
                action="Perform the planned verification.",
                expected_result="The expected outcome is observed.",
            )
        ],
        expected_result="The requirement is satisfied.",
        assumption_required=False,
        assumptions=[],
        source_basis=list(item.source_basis),
        traceability={
            "requirement_id": requirement.id,
            "coverage_item": item.coverage_item,
            "technique_used": item.technique_used,
        },
    )


def bundle_for(requirement, cases=None, status="SUCCESS"):
    return BundleModel(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        status=status,
        test_cases=cases if cases is not None else [case_for(requirement)],
        missing_information=[],
        assumptions=[],
        warnings=[],
        reason=None,
    )


async def run_engine(raw_requirements, mode="mvp_fast"):
    return await TestCaseEngine().generate(raw_requirements, mode=mode)


def test_generate_normal_one_requirement_success(monkeypatch):
    raw = [raw_requirement()]
    req = requirement_from_raw(raw[0])

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: bundle_for(req)}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine(raw))

    assert result.status == "SUCCESS"
    assert result.results[0].status == "SUCCESS"
    assert result.budget.calls_used == 3


def test_generate_multiple_requirements_one_chunk_uses_one_planner_and_generator(monkeypatch):
    raw = [raw_requirement("REQ_1"), raw_requirement("REQ_2")]
    calls = {"planner": 0, "generator": 0}

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        calls["planner"] += 1
        return {requirement.id: plan_for(requirement) for requirement in requirements}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        calls["generator"] += 1
        return {req.id: bundle_for(req) for req in requirements}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine(raw))

    assert result.status == "SUCCESS"
    assert calls == {"planner": 1, "generator": 1}


def test_blocked_planner_output_does_not_call_generator(monkeypatch):
    raw = [raw_requirement()]
    generator_calls = []

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req, safe=False) for req in requirements}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        generator_calls.append(requirements)
        return {}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine(raw))

    assert generator_calls == []
    assert result.status == "BLOCKED_MISSING_INFORMATION"


def test_mixed_safe_and_blocked_calls_generator_only_for_safe(monkeypatch):
    raw = [raw_requirement("REQ_1"), raw_requirement("REQ_2")]
    generator_ids = []

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {
            requirements[0].id: plan_for(requirements[0]),
            requirements[1].id: plan_for(requirements[1], safe=False),
        }

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        generator_ids.extend(req.id for req in requirements)
        return {req.id: bundle_for(req) for req in requirements}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine(raw))

    assert generator_ids == ["REQ_1"]
    assert result.status == "NEEDS_REVIEW"


def test_generated_bundle_is_validated_through_phase5(monkeypatch):
    raw = [raw_requirement()]

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {requirement.id: plan_for(requirement) for requirement in requirements}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        req = requirements[0]
        bad_case = case_for(req)
        bad_case.traceability = {
            "requirement_id": req.id,
            "coverage_item": "Unplanned coverage",
            "technique_used": "Functional verification",
        }
        return {req.id: bundle_for(req, [bad_case])}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine(raw))

    assert result.results[0].status == "FAILED_SCHEMA_VALIDATION"


def test_invalid_generated_bundle_becomes_failed_schema(monkeypatch):
    raw = [raw_requirement()]

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {requirement.id: plan_for(requirement) for requirement in requirements}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        req = requirements[0]
        bad_case = case_for(req)
        bad_case.title = " "
        return {req.id: bundle_for(req, [bad_case])}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine(raw))

    assert result.results[0].status == "FAILED_SCHEMA_VALIDATION"


def test_generator_overproduces_and_validation_trims(monkeypatch):
    raw = [raw_requirement()]

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req, count=1) for req in requirements}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        req = requirements[0]
        return {
            req.id: bundle_for(
                req,
                [case_for(req, "TC_REQ_1_001"), case_for(req, "TC_REQ_1_002")],
            )
        }

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine(raw))

    assert result.status == "NEEDS_REVIEW"
    assert len(result.results[0].test_cases) == 1


def test_all_blocked_results_overall_status_blocked():
    assert determine_overall_status(
        [BundleModel("REQ_1", "Text", "FR", "BLOCKED_MISSING_INFORMATION", [], [], [], [])],
        [],
    ) == "BLOCKED_MISSING_INFORMATION"


def test_all_success_results_overall_status_success():
    assert determine_overall_status(
        [BundleModel("REQ_1", "Text", "FR", "SUCCESS", [case_for(RequirementForTestCase("REQ_1", "Text", "FR"))], [], [], [])],
        [],
    ) == "SUCCESS"


def test_mixed_success_and_blocked_overall_status_needs_review():
    req = RequirementForTestCase("REQ_1", "Text", "FR")
    assert determine_overall_status(
        [
            BundleModel("REQ_1", "Text", "FR", "SUCCESS", [case_for(req)], [], [], []),
            BundleModel("REQ_2", "Text", "FR", "BLOCKED_MISSING_INFORMATION", [], [], [], []),
        ],
        [],
    ) == "NEEDS_REVIEW"


def test_provider_failed_bundle_overall_status_provider_failed():
    assert determine_overall_status(
        [BundleModel("REQ_1", "Text", "FR", "PROVIDER_FAILED", [], [], [], [])],
        [],
    ) == "PROVIDER_FAILED"


def test_invalid_raw_input_returns_failed_schema_with_warning():
    result = asyncio.run(TestCaseEngine().generate([{"id": "REQ_1"}]))

    assert result.status == "FAILED_SCHEMA_VALIDATION"
    assert result.results == []
    assert result.warnings


def test_too_many_requirements_returns_failed_schema_with_warning():
    raw = [raw_requirement(f"REQ_{index}") for index in range(1, 5)]

    result = asyncio.run(run_engine(raw))

    assert result.status == "FAILED_SCHEMA_VALIDATION"
    assert result.warnings == ["mode mvp_fast allows at most 3 requirements"]


def test_invalid_mode_returns_failed_schema_with_warning():
    result = asyncio.run(TestCaseEngine().generate([raw_requirement()], mode="slow"))

    assert result.status == "FAILED_SCHEMA_VALIDATION"
    assert result.warnings


def test_budget_calls_used_is_three_when_one_chunk_has_safe_requirements(monkeypatch):
    raw = [raw_requirement()]

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {requirement.id: plan_for(requirement) for requirement in requirements}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: bundle_for(req) for req in requirements}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine(raw))

    assert result.budget.calls_used == 3


def test_budget_calls_used_is_one_when_one_chunk_all_blocked(monkeypatch):
    raw = [raw_requirement()]

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req, safe=False) for req in requirements}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    result = asyncio.run(run_engine(raw))

    assert result.budget.calls_used == 1


def test_mvp_fast_with_three_requirements_one_planner_and_generator(monkeypatch):
    raw = [raw_requirement(f"REQ_{index}") for index in range(1, 4)]
    calls = {"planner": 0, "generator": 0}

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        calls["planner"] += 1
        return {requirement.id: plan_for(requirement) for requirement in requirements}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        calls["generator"] += 1
        return {req.id: bundle_for(req) for req in requirements}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine(raw))

    assert result.status == "SUCCESS"
    assert calls == {"planner": 1, "generator": 1}


def test_balanced_with_three_requirements_one_planner_and_generator(monkeypatch):
    raw = [raw_requirement(f"REQ_{index}") for index in range(1, 4)]
    calls = {"planner": 0, "generator": 0}

    async def fake_plan_batch(requirements, project_context=None, mode="balanced"):
        calls["planner"] += 1
        return {requirement.id: plan_for(requirement) for requirement in requirements}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="balanced"):
        calls["generator"] += 1
        return {req.id: bundle_for(req) for req in requirements}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine(raw, mode="balanced"))

    assert result.status == "SUCCESS"
    assert calls == {"planner": 1, "generator": 1}


def test_generate_batch_unexpected_exception_creates_provider_failed(monkeypatch):
    raw = [raw_requirement()]

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {requirement.id: plan_for(requirement) for requirement in requirements}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine(raw))

    assert result.status == "PROVIDER_FAILED"
    assert result.results[0].status == "PROVIDER_FAILED"


def test_plan_batch_unexpected_exception_creates_provider_fallback(monkeypatch):
    raw = [raw_requirement()]

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    result = asyncio.run(run_engine(raw))

    assert result.status == "PROVIDER_FAILED"
    assert result.results[0].status == "PROVIDER_FAILED"


def test_no_endpoint_is_added_in_main_by_this_phase():
    text = Path("app/services/test_case_generation/orchestrator.py").read_text()
    assert "@app.post" not in text


def test_no_text_content_inspection_is_used():
    text = Path("app/services/test_case_generation/orchestrator.py").read_text()
    assert ".lower(" not in text
    assert "call_llm" not in text

