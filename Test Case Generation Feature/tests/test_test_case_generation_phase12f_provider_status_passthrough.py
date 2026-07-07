import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.services.test_case_generation.cache import cache_stats, clear_test_case_cache
from app.services.test_case_generation.generator import generate_batch, make_failed_bundle
from app.services.test_case_generation.models import (
    CoverageItem,
    GenerationBudget,
    PlannerOutput,
    RequirementReviewResult,
    RequirementForTestCase,
    TestCase as CaseModel,
    TestCaseBundle as BundleModel,
    TestCaseGenerationResult as ResultModel,
    TestCaseReviewDecision as ReviewDecisionModel,
    TestStep as StepModel,
)
from app.services.test_case_generation.orchestrator import (
    TestCaseEngine,
    determine_overall_status,
    is_terminal_provider_bundle,
)
from app.services.test_case_generation.planner import parse_planner_response, plan_batch


client = TestClient(main.app)


class StatusCode429Error(Exception):
    status_code = 429


class QuotaError(Exception):
    pass


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
        "requirement": f"The system shall process item {requirement_id}.",
        "classification_type": classification_type,
    }


def requirement_model(raw=None):
    raw = raw or raw_requirement()
    return RequirementForTestCase(
        id=raw["id"],
        requirement=raw["requirement"],
        classification_type=raw["classification_type"],
    )


def coverage_item():
    return CoverageItem(
        coverage_item="Verify stated behavior.",
        source_basis=["The system shall process item REQ_1."],
        test_type="Positive",
        technique_used="Functional verification",
        priority="High",
        rationale="Covers planned behavior.",
    )


def plan_for(requirement, safe=True):
    return PlannerOutput(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        testable=safe,
        safe_to_generate=safe,
        risk_level="Medium",
        ambiguity_level="Low" if safe else "High",
        blocking_missing_information=[] if safe else ["Missing detail"],
        missing_information=[],
        coverage_items=[coverage_item()] if safe else [],
        recommended_test_case_count=1 if safe else 0,
        assumptions=[],
    )


def plan_dict(requirement, **overrides):
    data = {
        "requirement_id": requirement.id,
        "requirement_text": requirement.requirement,
        "requirement_type": requirement.classification_type,
        "testable": True,
        "safe_to_generate": True,
        "risk_level": "Medium",
        "ambiguity_level": "Low",
        "blocking_missing_information": [],
        "missing_information": [],
        "coverage_items": [
            {
                "coverage_item": "Verify stated behavior.",
                "source_basis": ["The system shall process item REQ_1."],
                "test_type": "Positive",
                "technique_used": "Functional verification",
                "priority": "High",
                "rationale": "Covers planned behavior.",
            }
        ],
        "recommended_test_case_count": 1,
        "assumptions": [],
    }
    data.update(overrides)
    return data


def case_for(requirement, title="Verify planned behavior"):
    item = coverage_item()
    return CaseModel(
        test_case_id=f"TC_{requirement.id}_001",
        requirement_id=requirement.id,
        title=title,
        objective="Confirm the requirement is satisfied.",
        test_type=item.test_type,
        technique_used=item.technique_used,
        priority=item.priority,
        preconditions=["System is available."],
        test_data={},
        steps=[
            StepModel(
                step_number=1,
                action="Perform verification.",
                expected_result="Expected outcome is observed.",
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


def bundle_for(requirement, status="SUCCESS", cases=None):
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


def result_for_status(status):
    req = requirement_model()
    return ResultModel(
        status=status,
        results=[bundle_for(req, status=status, cases=[])],
        plans=[plan_for(req)],
        warnings=[],
        budget=GenerationBudget(
            mode="mvp_fast",
            estimated_calls=2,
            estimated_tokens=1200,
            calls_used=1,
        ),
    )


def response_for(raw_plan):
    return {"plans": {"1": raw_plan}}


async def run_engine(raw_requirements=None):
    return await TestCaseEngine().generate(raw_requirements or [raw_requirement()])


def test_plan_batch_propagates_call_llm_runtime_error(monkeypatch):
    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise RuntimeError("provider failed")

    monkeypatch.setattr("app.services.test_case_generation.planner.call_llm", fake_call_llm)

    with pytest.raises(RuntimeError):
        asyncio.run(plan_batch([requirement_model()]))


def test_plan_batch_propagates_429_exception(monkeypatch):
    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise StatusCode429Error("limited")

    monkeypatch.setattr("app.services.test_case_generation.planner.call_llm", fake_call_llm)

    with pytest.raises(StatusCode429Error):
        asyncio.run(plan_batch([requirement_model()]))


def test_parse_planner_response_malformed_json_still_returns_blocked_plan():
    req = requirement_model()

    result = parse_planner_response("not json", [req])

    assert result[req.id].blocking_missing_information == [
        "Planner output could not be parsed. Retry generation."
    ]


def test_parse_planner_response_invalid_plan_still_returns_invalid_output():
    req = requirement_model()

    result = parse_planner_response(
        response_for(plan_dict(req, recommended_test_case_count=0)),
        [req],
    )

    assert result[req.id].blocking_missing_information[0][: len("Invalid planner output:")] == "Invalid planner output:"


def test_orchestrator_maps_planner_runtime_error_to_provider_failed(monkeypatch):
    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        raise RuntimeError("provider failed")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    result = asyncio.run(run_engine())

    assert result.status == "PROVIDER_FAILED"
    assert result.results[0].status == "PROVIDER_FAILED"


def test_orchestrator_maps_planner_429_exception_to_rate_limited(monkeypatch):
    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        raise StatusCode429Error("limited")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    result = asyncio.run(run_engine())

    assert result.status == "RATE_LIMITED"
    assert result.results[0].status == "RATE_LIMITED"


def test_planner_provider_failure_is_not_blocked(monkeypatch):
    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        raise RuntimeError("provider failed")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    result = asyncio.run(run_engine())

    assert result.results[0].status != "BLOCKED_MISSING_INFORMATION"


def test_planner_provider_failure_result_is_not_cached(monkeypatch):
    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        raise RuntimeError("provider failed")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    asyncio.run(run_engine())

    assert cache_stats()["size"] == 0


def test_second_identical_request_after_planner_failure_retries(monkeypatch):
    calls = {"planner": 0}

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        calls["planner"] += 1
        raise RuntimeError("provider failed")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    engine = TestCaseEngine()

    asyncio.run(engine.generate([raw_requirement()]))
    asyncio.run(engine.generate([raw_requirement()]))

    assert calls["planner"] == 2


def test_generate_batch_call_llm_runtime_error_returns_provider_failed(monkeypatch):
    req = requirement_model()
    plans = {req.id: plan_for(req)}

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise RuntimeError("provider failed")

    monkeypatch.setattr("app.services.test_case_generation.generator.call_llm", fake_call_llm)

    result = asyncio.run(generate_batch([req], plans))

    assert result[req.id].status == "PROVIDER_FAILED"


def test_orchestrator_preserves_generated_provider_failed_without_validation(monkeypatch):
    req = requirement_model()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {
            req.id: make_failed_bundle(
                req,
                "PROVIDER_FAILED",
                "Generator LLM call failed",
                plans[req.id],
            )
        }

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine())

    assert result.results[0].status == "PROVIDER_FAILED"


def test_generated_provider_failed_does_not_become_failed_schema(monkeypatch):
    req = requirement_model()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: make_failed_bundle(req, "PROVIDER_FAILED", "Generator LLM call failed", plans[req.id])}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine())

    assert result.status == "PROVIDER_FAILED"
    assert result.results[0].status != "FAILED_SCHEMA_VALIDATION"


def test_generated_provider_failed_keeps_generator_warning(monkeypatch):
    req = requirement_model()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: make_failed_bundle(req, "PROVIDER_FAILED", "Generator LLM call failed", plans[req.id])}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine())

    assert "Generator LLM call failed" in result.results[0].warnings


def test_generated_provider_failed_result_is_not_cached(monkeypatch):
    req = requirement_model()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: make_failed_bundle(req, "PROVIDER_FAILED", "Generator LLM call failed", plans[req.id])}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    asyncio.run(run_engine())

    assert cache_stats()["size"] == 0


def test_generate_batch_429_exception_returns_rate_limited(monkeypatch):
    req = requirement_model()
    plans = {req.id: plan_for(req)}

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise StatusCode429Error("limited")

    monkeypatch.setattr("app.services.test_case_generation.generator.call_llm", fake_call_llm)

    result = asyncio.run(generate_batch([req], plans))

    assert result[req.id].status == "RATE_LIMITED"


def test_orchestrator_preserves_generated_rate_limited_without_validation(monkeypatch):
    req = requirement_model()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: make_failed_bundle(req, "RATE_LIMITED", "Generator LLM call rate-limited", plans[req.id])}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine())

    assert result.status == "RATE_LIMITED"
    assert result.results[0].status == "RATE_LIMITED"


def test_generated_rate_limited_does_not_become_failed_schema(monkeypatch):
    req = requirement_model()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: make_failed_bundle(req, "RATE_LIMITED", "Generator LLM call rate-limited", plans[req.id])}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine())

    assert result.results[0].status != "FAILED_SCHEMA_VALIDATION"


def test_generated_rate_limited_result_is_not_cached(monkeypatch):
    req = requirement_model()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: make_failed_bundle(req, "RATE_LIMITED", "Generator LLM call rate-limited", plans[req.id])}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    asyncio.run(run_engine())

    assert cache_stats()["size"] == 0


def test_normal_success_bundle_is_still_validated(monkeypatch):
    req = requirement_model()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: bundle_for(req)}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine())

    assert result.status == "SUCCESS"
    assert len(result.results[0].test_cases) == 1


def test_invalid_generated_test_case_still_becomes_failed_schema(monkeypatch):
    req = requirement_model()
    bad_case = case_for(req, title=" ")

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: bundle_for(req, cases=[bad_case])}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(run_engine())

    assert result.results[0].status == "FAILED_SCHEMA_VALIDATION"


def test_malformed_generator_json_still_becomes_failed_schema(monkeypatch):
    req = requirement_model()
    plans = {req.id: plan_for(req)}

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        return "not json"

    monkeypatch.setattr("app.services.test_case_generation.generator.call_llm", fake_call_llm)

    result = asyncio.run(generate_batch([req], plans))

    assert result[req.id].status == "FAILED_SCHEMA_VALIDATION"


def test_provider_terminal_bundles_are_the_only_validation_bypass():
    assert is_terminal_provider_bundle(make_failed_bundle(requirement_model(), "PROVIDER_FAILED", "failed"))
    assert is_terminal_provider_bundle(make_failed_bundle(requirement_model(), "RATE_LIMITED", "limited"))
    assert not is_terminal_provider_bundle(bundle_for(requirement_model()))


def test_validation_py_unchanged_for_phase12f():
    text = Path("app/services/test_case_generation/validation.py").read_text()

    assert "PROVIDER_FAILED" not in text
    assert "RATE_LIMITED" not in text


def test_determine_overall_status_prioritizes_rate_limited_over_provider_failed():
    req = requirement_model()

    assert determine_overall_status(
        [
            bundle_for(req, status="PROVIDER_FAILED", cases=[]),
            bundle_for(req, status="RATE_LIMITED", cases=[]),
        ],
        [],
    ) == "RATE_LIMITED"


def test_determine_overall_status_returns_provider_failed_without_rate_limit():
    req = requirement_model()

    assert determine_overall_status([bundle_for(req, status="PROVIDER_FAILED", cases=[])], []) == "PROVIDER_FAILED"


def test_determine_overall_status_still_returns_blocked_for_deliberate_block():
    req = requirement_model()

    assert determine_overall_status(
        [bundle_for(req, status="BLOCKED_MISSING_INFORMATION", cases=[])],
        [],
    ) == "BLOCKED_MISSING_INFORMATION"


def test_determine_overall_status_still_returns_failed_schema_for_all_schema_failures():
    req = requirement_model()

    assert determine_overall_status(
        [bundle_for(req, status="FAILED_SCHEMA_VALIDATION", cases=[])],
        [],
    ) == "FAILED_SCHEMA_VALIDATION"


def test_generate_test_cases_can_return_provider_failed_json(monkeypatch):
    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        return result_for_status("PROVIDER_FAILED")

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post("/generate_test_cases", json={"requirements": [raw_requirement()]})

    assert response.status_code == 200
    assert response.json()["status"] == "PROVIDER_FAILED"


def test_generate_test_cases_can_return_rate_limited_json(monkeypatch):
    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        return result_for_status("RATE_LIMITED")

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post("/generate_test_cases", json={"requirements": [raw_requirement()]})

    assert response.status_code == 200
    assert response.json()["status"] == "RATE_LIMITED"


def test_generate_test_cases_estimate_still_makes_zero_engine_call(monkeypatch):
    calls = []

    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        calls.append(raw_requirements)
        return result_for_status("SUCCESS")

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post("/generate_test_cases/estimate", json={"requirements": [raw_requirement()]})

    assert response.status_code == 200
    assert calls == []


def test_phase12f_files_contain_no_requirement_lower():
    combined = "\n".join(
        Path(path).read_text()
        for path in [
            "app/services/test_case_generation/planner.py",
            "app/services/test_case_generation/orchestrator.py",
            "app/services/test_case_generation/errors.py",
            "tests/test_test_case_generation_phase12f_provider_status_passthrough.py",
        ]
    )

    assert "requirement" + "." + "low" + "er(" not in combined


def test_phase12f_files_contain_no_business_keyword_branching():
    combined = "\n".join(
        Path(path).read_text()
        for path in [
            "app/services/test_case_generation/planner.py",
            "app/services/test_case_generation/orchestrator.py",
            "app/services/test_case_generation/errors.py",
            "tests/test_test_case_generation_phase12f_provider_status_passthrough.py",
        ]
    )
    forbidden = [
        'if "' + "login" + '" in',
        'if "' + "password" + '" in',
        'if "' + "payment" + '" in',
        'if "' + "security" + '" in',
        "keyword-to" + "-test-type maps",
        "keyword-to" + "-technique maps",
        "hardcoded business" + "/domain routing",
    ]

    for fragment in forbidden:
        assert fragment not in combined


def test_no_phase12f_test_imports_groq_provider_directly():
    text = Path("tests/test_test_case_generation_phase12f_provider_status_passthrough.py").read_text()

    assert "Groq" + "Provider" not in text

