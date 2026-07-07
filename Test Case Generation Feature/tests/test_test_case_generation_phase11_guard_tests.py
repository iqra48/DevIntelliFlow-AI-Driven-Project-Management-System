import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.services.test_case_generation.cache import cache_stats, clear_test_case_cache
from app.services.test_case_generation.errors import (
    is_rate_limit_error,
    provider_status_from_exception,
)
from app.services.test_case_generation.generator import generate_batch
from app.services.test_case_generation.models import (
    CoverageItem,
    GenerationBudget,
    PlannerOutput,
    RequirementForTestCase,
    TestCase as CaseModel,
    TestCaseBundle as BundleModel,
    TestCaseGenerationResult as ResultModel,
    TestStep as StepModel,
)
from app.services.test_case_generation.orchestrator import (
    TestCaseEngine,
    determine_overall_status,
)


client = TestClient(main.app)


def setup_function():
    clear_test_case_cache()


def teardown_function():
    clear_test_case_cache()


class StatusCodeError(Exception):
    status_code = 429


class ResponseStatusCodeError(Exception):
    def __init__(self):
        super().__init__("provider failed")
        self.response = type("Response", (), {"status_code": 429})()


class CodeError(Exception):
    code = 429


class RateLimitError(Exception):
    pass


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


def case_for(requirement):
    item = coverage_item()
    return CaseModel(
        test_case_id=f"TC_{requirement.id}_001",
        requirement_id=requirement.id,
        title="Verify planned behavior",
        objective="Confirm the requirement is satisfied.",
        test_type=item.test_type,
        technique_used=item.technique_used,
        priority=item.priority,
        preconditions=["System is available."],
        test_data={},
        steps=[
            TestStep(
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


def bundle_for(requirement, status="SUCCESS"):
    return BundleModel(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        status=status,
        test_cases=[case_for(requirement)] if status == "SUCCESS" else [],
        missing_information=[],
        assumptions=[],
        warnings=[],
        reason=None,
    )


def result_for_status(status="RATE_LIMITED"):
    raw = raw_requirement()
    requirement = requirement_model(raw)
    bundle = bundle_for(requirement, status=status)
    return ResultModel(
        status=status,
        results=[bundle],
        plans=[plan_for(requirement)],
        warnings=[],
        budget=GenerationBudget(
            mode="mvp_fast",
            estimated_calls=2,
            estimated_tokens=1200,
            calls_used=1,
        ),
    )


def test_is_rate_limit_error_true_for_status_code_429():
    assert is_rate_limit_error(StatusCodeError())


def test_is_rate_limit_error_true_for_response_status_code_429():
    assert is_rate_limit_error(ResponseStatusCodeError())


def test_is_rate_limit_error_true_for_code_429():
    assert is_rate_limit_error(CodeError())


def test_is_rate_limit_error_true_for_rate_limit_class_name():
    assert is_rate_limit_error(RateLimitError())


def test_is_rate_limit_error_true_for_rate_limit_message():
    assert is_rate_limit_error(RuntimeError("provider rate limit reached"))


def test_is_rate_limit_error_true_for_too_many_requests_message():
    assert is_rate_limit_error(RuntimeError("too many requests"))


def test_is_rate_limit_error_true_for_quota_message():
    assert is_rate_limit_error(RuntimeError("quota exceeded"))


def test_is_rate_limit_error_false_for_generic_runtime_error():
    assert not is_rate_limit_error(RuntimeError("provider unavailable"))


def test_provider_status_from_exception_returns_rate_limited_for_429():
    assert provider_status_from_exception(StatusCodeError()) == "RATE_LIMITED"


def test_provider_status_from_exception_returns_provider_failed_for_generic_exception():
    assert provider_status_from_exception(RuntimeError("provider unavailable")) == "PROVIDER_FAILED"


def test_generate_batch_returns_rate_limited_bundle_when_call_llm_raises_429(monkeypatch):
    requirement = requirement_model()
    plans = {requirement.id: plan_for(requirement)}

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise StatusCodeError("provider limited")

    monkeypatch.setattr("app.services.test_case_generation.generator.call_llm", fake_call_llm)

    result = asyncio.run(generate_batch([requirement], plans))

    assert result[requirement.id].status == "RATE_LIMITED"


def test_rate_limited_generator_bundle_has_no_test_cases(monkeypatch):
    requirement = requirement_model()
    plans = {requirement.id: plan_for(requirement)}

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise StatusCodeError("provider limited")

    monkeypatch.setattr("app.services.test_case_generation.generator.call_llm", fake_call_llm)

    result = asyncio.run(generate_batch([requirement], plans))

    assert result[requirement.id].test_cases == []


def test_rate_limited_generator_bundle_preserves_requirement_identity(monkeypatch):
    requirement = requirement_model()
    plans = {requirement.id: plan_for(requirement)}

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise StatusCodeError("provider limited")

    monkeypatch.setattr("app.services.test_case_generation.generator.call_llm", fake_call_llm)

    result = asyncio.run(generate_batch([requirement], plans))[requirement.id]

    assert result.requirement_id == requirement.id
    assert result.requirement_text == requirement.requirement
    assert result.requirement_type == requirement.classification_type


def test_generic_generator_exception_still_returns_provider_failed(monkeypatch):
    requirement = requirement_model()
    plans = {requirement.id: plan_for(requirement)}

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.services.test_case_generation.generator.call_llm", fake_call_llm)

    result = asyncio.run(generate_batch([requirement], plans))

    assert result[requirement.id].status == "PROVIDER_FAILED"


def test_unexpected_plan_batch_429_exception_returns_overall_rate_limited(monkeypatch):
    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        raise StatusCodeError("provider limited")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.status == "RATE_LIMITED"
    assert result.results[0].status == "RATE_LIMITED"


def test_unexpected_generate_batch_429_exception_returns_overall_rate_limited(monkeypatch):
    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {requirement.id: plan_for(requirement) for requirement in requirements}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        raise StatusCodeError("provider limited")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.status == "RATE_LIMITED"
    assert result.results[0].status == "RATE_LIMITED"


def test_rate_limited_result_is_not_stored_in_cache(monkeypatch):
    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        raise StatusCodeError("provider limited")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert cache_stats()["size"] == 0


def test_second_identical_request_after_rate_limited_retries_pipeline(monkeypatch):
    calls = {"planner": 0}

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        calls["planner"] += 1
        raise StatusCodeError("provider limited")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    engine = TestCaseEngine()

    asyncio.run(engine.generate([raw_requirement()]))
    asyncio.run(engine.generate([raw_requirement()]))

    assert calls["planner"] == 2


def test_generic_provider_exception_remains_provider_failed(monkeypatch):
    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.status == "PROVIDER_FAILED"
    assert result.results[0].status == "PROVIDER_FAILED"


def test_determine_overall_status_prioritizes_rate_limited():
    requirement = requirement_model()

    assert determine_overall_status(
        [
            bundle_for(requirement, status="PROVIDER_FAILED"),
            bundle_for(requirement, status="RATE_LIMITED"),
        ],
        [],
    ) == "RATE_LIMITED"


def test_generate_test_cases_returns_rate_limited_structured_response(monkeypatch):
    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        return result_for_status("RATE_LIMITED")

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases",
        json={"requirements": [raw_requirement()], "mode": "mvp_fast"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "RATE_LIMITED"
    assert response.json()["results"][0]["status"] == "RATE_LIMITED"


def test_generate_test_cases_invalid_request_fails_before_engine_call(monkeypatch):
    calls = []

    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        calls.append(raw_requirements)
        return result_for_status("SUCCESS")

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases",
        json={"requirements": [{"id": "REQ_1", "classification_type": "FR"}]},
    )

    assert response.json()["status"] == "FAILED_SCHEMA_VALIDATION"
    assert calls == []


def test_generate_test_cases_estimate_makes_zero_engine_call(monkeypatch):
    calls = []

    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        calls.append(raw_requirements)
        return result_for_status("SUCCESS")

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases/estimate",
        json={"requirements": [raw_requirement()]},
    )

    assert response.status_code == 200
    assert calls == []


def test_process_and_process_file_routes_still_exist():
    routes = {route.path: route for route in main.app.routes}

    assert "/process" in routes
    assert "POST" in routes["/process"].methods
    assert "/process_file" in routes
    assert "POST" in routes["/process_file"].methods


def test_no_live_llm_call_when_generator_has_no_safe_requirements(monkeypatch):
    requirement = requirement_model()
    plans = {requirement.id: plan_for(requirement, safe=False)}

    async def fail_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise AssertionError("live LLM should not be called")

    monkeypatch.setattr("app.services.test_case_generation.generator.call_llm", fail_call_llm)

    result = asyncio.run(generate_batch([requirement], plans))

    assert result[requirement.id].status == "NEEDS_REVIEW"


def test_no_phase11_test_imports_groq_provider_directly():
    text = Path("tests/test_test_case_generation_phase11_guard_tests.py").read_text()

    provider_name = "Groq" + "Provider"
    assert provider_name not in text


def test_no_phase11_test_requires_network():
    text = Path("tests/test_test_case_generation_phase11_guard_tests.py").read_text()

    assert "requests" + "." not in text
    assert "httpx" + "." not in text


def test_phase11_files_contain_no_requirement_lower():
    combined = "\n".join(
        Path(path).read_text()
        for path in [
            "app/services/test_case_generation/errors.py",
            "app/services/test_case_generation/generator.py",
            "app/services/test_case_generation/orchestrator.py",
            "tests/test_test_case_generation_phase11_guard_tests.py",
        ]
    )

    forbidden = "requirement" + ".lower("
    assert forbidden not in combined


def test_phase11_files_contain_no_business_keyword_branching():
    combined = "\n".join(
        Path(path).read_text()
        for path in [
            "app/services/test_case_generation/errors.py",
            "app/services/test_case_generation/generator.py",
            "app/services/test_case_generation/orchestrator.py",
            "tests/test_test_case_generation_phase11_guard_tests.py",
        ]
    )

    forbidden_fragments = [
        'if "' + "login" + '" in',
        'if "' + "password" + '" in',
        'if "' + "payment" + '" in',
        "keyword-to" + "-test-type maps",
        "keyword-to" + "-technique maps",
        "hardcoded business" + "/domain routing",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in combined


def test_errors_py_does_not_import_llm_providers():
    text = Path("app/services/test_case_generation/errors.py").read_text()

    assert "Groq" + "Provider" not in text
    assert "Ollama" + "Provider" not in text
    assert "llm_router" not in text

