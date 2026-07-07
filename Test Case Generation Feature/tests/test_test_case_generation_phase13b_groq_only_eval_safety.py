import asyncio
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
import scripts.run_test_case_evaluation as eval_script
from app.services.test_case_generation.cache import clear_test_case_cache
from app.services.test_case_generation.generator import generate_batch
from app.services.test_case_generation.models import (
    CoverageItem,
    PlannerOutput,
    RequirementForTestCase,
    RequirementReviewResult,
    TestCase as CaseModel,
    TestCaseBundle as BundleModel,
    TestCaseReviewDecision as ReviewDecisionModel,
    TestStep as StepModel,
)
from app.services.test_case_generation.orchestrator import TestCaseEngine
from app.shared.llm.llm_router import GroqGovernorLimitExceeded
from app.shared.llm.exceptions import StrictProviderFallbackBlocked


client = TestClient(main.app)


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


def plan_for(requirement):
    item = coverage_item()
    return PlannerOutput(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
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


def bundle_for(requirement):
    return BundleModel(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        status="SUCCESS",
        test_cases=[case_for(requirement)],
        missing_information=[],
        assumptions=[],
        warnings=[],
        reason=None,
    )


def keep_review(requirement, bundle):
    return RequirementReviewResult(
        requirement_id=requirement.id,
        decisions=[
            ReviewDecisionModel(
                requirement_id=requirement.id,
                test_case_id=test_case.test_case_id,
                decision="KEEP",
                reason="Kept for test.",
                unsupported_elements=[],
                required_human_review=False,
            )
            for test_case in bundle.test_cases
        ],
        warnings=[],
    )


def test_planner_local_governor_block_maps_to_rate_limited(monkeypatch):
    clear_test_case_cache()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        raise GroqGovernorLimitExceeded("Groq local governor cap exceeded")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.status == "RATE_LIMITED"
    assert result.results[0].status == "RATE_LIMITED"
    assert "governor" in result.results[0].reason.casefold()


def test_generator_local_governor_block_maps_to_rate_limited(monkeypatch):
    req = requirement_model()

    async def fake_call_llm(prompt, system_prompt=None, model=None, num_predict=None):
        raise GroqGovernorLimitExceeded("Groq local governor cap exceeded")

    monkeypatch.setattr("app.services.test_case_generation.generator.call_llm", fake_call_llm)

    result = asyncio.run(generate_batch([req], {req.id: plan_for(req)}))

    assert result[req.id].status == "RATE_LIMITED"
    assert "governor" in result[req.id].reason.casefold()


def test_reviewer_local_governor_block_adds_clear_warning(monkeypatch):
    clear_test_case_cache()
    req = requirement_model()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: bundle_for(req)}

    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        raise GroqGovernorLimitExceeded("Groq local governor cap exceeded")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.status == "NEEDS_REVIEW"
    assert "Reviewer unavailable because Groq-only provider was blocked by governor" in result.results[0].warnings


def test_generate_test_cases_does_not_return_success_when_strict_groq_is_blocked(monkeypatch):
    clear_test_case_cache()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        raise GroqGovernorLimitExceeded("Groq local governor cap exceeded")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    response = client.post("/generate_test_cases", json={"requirements": [raw_requirement()]})
    body = response.json()

    assert body["status"] == "RATE_LIMITED"
    assert body["status"] != "SUCCESS"


def test_estimate_endpoint_still_has_no_llm_call(monkeypatch):
    async def fail_generate(raw_requirements, project_context=None, mode="mvp_fast"):
        raise AssertionError("estimate must not call generation")

    monkeypatch.setattr(main.test_case_engine, "generate", fail_generate)

    response = client.post("/generate_test_cases/estimate", json={"requirements": [raw_requirement()]})

    assert response.status_code == 200
    assert response.json()["allowed"] is True


def test_calls_used_is_honest_when_local_governor_blocks(monkeypatch):
    clear_test_case_cache()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        raise GroqGovernorLimitExceeded("Groq local governor cap exceeded")

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.budget.calls_used == 1


def test_require_groq_only_fails_if_provider_is_not_groq(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "true")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_test_case_evaluation.py",
            "--live",
            "--limit",
            "0",
            "--reports-dir",
            str(tmp_path),
            "--require-groq-only",
        ],
    )

    assert eval_script.main() == 2
    assert "LLM_PROVIDER must be groq" in capsys.readouterr().out


def test_require_groq_only_fails_if_strict_provider_is_not_true(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "false")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_test_case_evaluation.py",
            "--live",
            "--limit",
            "0",
            "--reports-dir",
            str(tmp_path),
            "--require-groq-only",
        ],
    )

    assert eval_script.main() == 2
    assert "LLM_STRICT_PROVIDER must be true" in capsys.readouterr().out


def test_require_groq_only_prints_provider_settings(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "true")
    monkeypatch.setenv("GROQ_DAILY_TOKEN_LIMIT", "100000")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_test_case_evaluation.py",
            "--live",
            "--limit",
            "0",
            "--reports-dir",
            str(tmp_path),
            "--require-groq-only",
        ],
    )

    assert eval_script.main() == 0
    output = capsys.readouterr().out
    assert "provider=groq" in output
    assert "strict_provider=true" in output
    assert "groq_daily_token_limit=100000" in output
    assert "offset=0" in output
    assert "limit=0" in output


def test_offset_selects_requested_eval_window():
    items = [{"eval_id": f"EVAL_{index}"} for index in range(45)]

    selected = eval_script._select_eval_items(items, offset=20, limit=10)

    assert [item["eval_id"] for item in selected] == [
        "EVAL_20",
        "EVAL_21",
        "EVAL_22",
        "EVAL_23",
        "EVAL_24",
        "EVAL_25",
        "EVAL_26",
        "EVAL_27",
        "EVAL_28",
        "EVAL_29",
    ]


def test_offset_with_no_limit_selects_remaining_items():
    items = [{"eval_id": f"EVAL_{index}"} for index in range(45)]

    selected = eval_script._select_eval_items(items, offset=40, limit=None)

    assert [item["eval_id"] for item in selected] == [
        "EVAL_40",
        "EVAL_41",
        "EVAL_42",
        "EVAL_43",
        "EVAL_44",
    ]


def test_negative_offset_fails_fast(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_test_case_evaluation.py",
            "--dry-run",
            "--offset",
            "-1",
            "--reports-dir",
            str(tmp_path),
        ],
    )

    assert eval_script.main() == 2
    assert "offset must be >= 0" in capsys.readouterr().out


def test_negative_limit_fails_fast(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_test_case_evaluation.py",
            "--dry-run",
            "--limit",
            "-1",
            "--reports-dir",
            str(tmp_path),
        ],
    )

    assert eval_script.main() == 2
    assert "limit must be >= 0" in capsys.readouterr().out


def test_local_governor_cap_marks_groq_only_evaluation_incomplete():
    result = {
        "status": "RATE_LIMITED",
        "results": [
            {
                "warnings": ["Planner rate-limited: Groq local governor cap exceeded"],
                "reason": "Groq local governor cap exceeded",
            }
        ],
    }

    assert eval_script._is_local_groq_governor_result(result) is True


def test_reviewer_governor_warning_marks_groq_only_evaluation_incomplete():
    result = {
        "status": "NEEDS_REVIEW",
        "results": [
            {
                "warnings": [
                    "Reviewer unavailable because Groq-only provider was blocked by governor"
                ],
                "reason": None,
            }
        ],
    }

    assert eval_script._is_local_groq_governor_result(result) is True


def test_groq_rate_limit_warning_marks_groq_only_evaluation_incomplete():
    result = {
        "status": "NEEDS_REVIEW",
        "results": [
            {
                "warnings": [
                    "Reviewer unavailable because Groq-only provider hit a rate limit"
                ],
                "reason": None,
            }
        ],
    }

    assert (
        eval_script._groq_only_incomplete_reason(result)
        == "Groq-only evaluation incomplete: Groq rate limit reached"
    )


def test_reviewer_real_rate_limit_warning_is_not_local_governor(monkeypatch):
    clear_test_case_cache()
    req = requirement_model()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: bundle_for(req)}

    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        raise StrictProviderFallbackBlocked(
            "Groq-only provider failed; fallback providers are disabled. "
            "Original error [RateLimitError]: Error code: 429"
        )

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert "Reviewer unavailable because Groq-only provider hit a rate limit" in result.results[0].warnings
    assert "Reviewer unavailable because Groq-only provider was blocked by governor" not in result.results[0].warnings


def test_reviewer_strict_provider_failure_warning_marks_incomplete(monkeypatch):
    clear_test_case_cache()
    req = requirement_model()

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req)}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        return {req.id: bundle_for(req)}

    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        raise StrictProviderFallbackBlocked(
            "Groq-only provider failed; fallback providers are disabled. "
            "Original error [APIConnectionError]: Connection error."
        )

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))
    result_dict = result.to_dict()

    assert "Reviewer unavailable because Groq-only provider failed" in result.results[0].warnings
    assert (
        eval_script._groq_only_incomplete_reason(result_dict)
        == "Groq-only evaluation incomplete: Groq provider failed"
    )


def test_no_repairer_py_added():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_no_approved_status_added():
    text = Path("app/services/test_case_generation/models.py").read_text()

    assert '"APPROVED"' not in text
    assert "'APPROVED'" not in text

