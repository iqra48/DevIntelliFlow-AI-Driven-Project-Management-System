from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.services.test_case_generation.models import (
    CoverageItem,
    GenerationBudget,
    PlannerOutput,
    TestCase as CaseModel,
    TestCaseBundle as BundleModel,
    TestCaseGenerationResult as ResultModel,
    TestStep as StepModel,
)
from app.shared.llm.call_llm import request_budget_ctx, request_calls_ctx


client = TestClient(main.app)


def raw_requirement(requirement_id="REQ_1", classification_type="FR"):
    return {
        "id": requirement_id,
        "requirement": f"The system shall export report {requirement_id}.",
        "classification_type": classification_type,
    }


def fake_result(mode="mvp_fast", calls_used=2):
    req = raw_requirement()
    item = CoverageItem(
        coverage_item="Verify stated behavior.",
        source_basis=["The system shall export report REQ_1."],
        test_type="Positive",
        technique_used="Functional verification",
        priority="High",
        rationale="Covers planned behavior.",
    )
    plan = PlannerOutput(
        requirement_id=req["id"],
        requirement_text=req["requirement"],
        requirement_type=req["classification_type"],
        testable=True,
        safe_to_generate=True,
        risk_level="Medium",
        ambiguity_level="Low",
        blocking_missing_information=[],
        missing_information=[],
        coverage_items=[item],
        recommended_test_case_count=1,
        assumptions=[],
    )
    case = CaseModel(
        test_case_id="TC_REQ_1_001",
        requirement_id=req["id"],
        title="Verify report export",
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
            "requirement_id": req["id"],
            "coverage_item": item.coverage_item,
            "technique_used": item.technique_used,
        },
    )
    bundle = BundleModel(
        requirement_id=req["id"],
        requirement_text=req["requirement"],
        requirement_type=req["classification_type"],
        status="SUCCESS",
        test_cases=[case],
        missing_information=[],
        assumptions=[],
        warnings=[],
        reason=None,
    )
    return ResultModel(
        status="SUCCESS",
        results=[bundle],
        plans=[plan],
        warnings=[],
        budget=GenerationBudget(
            mode=mode,
            estimated_calls=2,
            estimated_tokens=1240,
            calls_used=calls_used,
        ),
    )


def test_generate_test_cases_valid_request_returns_200(monkeypatch):
    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        return fake_result(mode)

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases",
        json={"requirements": [raw_requirement()], "mode": "mvp_fast"},
    )

    assert response.status_code == 200


def test_valid_request_calls_engine_generate_once(monkeypatch):
    calls = []

    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        calls.append((raw_requirements, project_context, mode))
        return fake_result(mode)

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    client.post(
        "/generate_test_cases",
        json={
            "requirements": [raw_requirement()],
            "project_context": "Context",
            "mode": "mvp_fast",
        },
    )

    assert len(calls) == 1
    assert calls[0][1] == "Context"


def test_valid_request_returns_success_from_engine(monkeypatch):
    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        return fake_result(mode)

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases",
        json={"requirements": [raw_requirement()], "mode": "mvp_fast"},
    )

    assert response.json()["status"] == "SUCCESS"


def test_valid_request_sets_budget_calls_used_from_context_or_keeps_logical(monkeypatch):
    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        request_calls_ctx.set(1)
        return fake_result(mode, calls_used=2)

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases",
        json={"requirements": [raw_requirement()], "mode": "mvp_fast"},
    )

    assert response.json()["budget"]["calls_used"] == 1


def test_mixed_request_returns_failed_and_does_not_call_engine(monkeypatch):
    calls = []

    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        calls.append(raw_requirements)
        return fake_result(mode)

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases",
        json={"requirements": [raw_requirement(classification_type="MIXED")]},
    )

    assert response.json()["status"] == "FAILED_SCHEMA_VALIDATION"
    assert calls == []


def test_too_many_mvp_fast_requirements_returns_failed_and_does_not_call_engine(monkeypatch):
    calls = []

    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        calls.append(raw_requirements)
        return fake_result(mode)

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases",
        json={
            "requirements": [raw_requirement(f"REQ_{index}") for index in range(1, 5)]
        },
    )

    assert response.json()["status"] == "FAILED_SCHEMA_VALIDATION"
    assert calls == []


def test_invalid_mode_returns_failed_and_does_not_call_engine(monkeypatch):
    calls = []

    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        calls.append(raw_requirements)
        return fake_result(mode)

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases",
        json={"requirements": [raw_requirement()], "mode": "slow"},
    )

    assert response.json()["status"] == "FAILED_SCHEMA_VALIDATION"
    assert calls == []


def test_missing_requirement_field_returns_failed_and_does_not_call_engine(monkeypatch):
    calls = []

    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        calls.append(raw_requirements)
        return fake_result(mode)

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases",
        json={"requirements": [{"id": "REQ_1", "classification_type": "FR"}]},
    )

    assert response.json()["status"] == "FAILED_SCHEMA_VALIDATION"
    assert calls == []


def test_endpoint_response_is_json_serializable(monkeypatch):
    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        return fake_result(mode)

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases",
        json={"requirements": [raw_requirement()]},
    )

    assert response.headers["content-type"].startswith("application/json")
    assert isinstance(response.json(), dict)


def test_estimate_still_works():
    response = client.post(
        "/generate_test_cases/estimate",
        json={"requirements": [raw_requirement()]},
    )

    assert response.status_code == 200
    assert response.json()["allowed"] is True


def test_process_still_exists_and_route_is_unchanged():
    routes = {route.path: route for route in main.app.routes}

    assert "/process" in routes
    assert "POST" in routes["/process"].methods


def test_process_file_still_exists_and_route_is_unchanged():
    routes = {route.path: route for route in main.app.routes}

    assert "/process_file" in routes
    assert "POST" in routes["/process_file"].methods


def test_generation_endpoint_does_not_call_requirement_engine_process(monkeypatch):
    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        return fake_result(mode)

    async def fail_process(text):
        raise AssertionError("process should not be called")

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)
    monkeypatch.setattr(main.engine, "process", fail_process)

    response = client.post(
        "/generate_test_cases",
        json={"requirements": [raw_requirement()]},
    )

    assert response.json()["status"] == "SUCCESS"


def test_generation_endpoint_sets_request_budget_context_to_estimate_calls(monkeypatch):
    observed = []

    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        observed.append(request_budget_ctx.get())
        return fake_result(mode)

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    client.post(
        "/generate_test_cases",
        json={"requirements": [raw_requirement()]},
    )

    assert observed == [{"max_calls": 4}]


def test_engine_exception_returns_structured_provider_failed(monkeypatch):
    async def fake_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        request_calls_ctx.set(1)
        raise RuntimeError("engine failed")

    monkeypatch.setattr(main.test_case_engine, "generate", fake_generate)

    response = client.post(
        "/generate_test_cases",
        json={"requirements": [raw_requirement()]},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "PROVIDER_FAILED"
    assert body["budget"]["calls_used"] == 1


def test_no_keyword_or_domain_text_inspection_added_to_main():
    text = Path("app/main.py").read_text()

    assert ".lower(" not in text
    assert "test_case_engine.generate" in text

