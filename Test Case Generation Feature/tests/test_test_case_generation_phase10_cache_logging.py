import asyncio
import logging
import time
from pathlib import Path

import pytest

from app.services.test_case_generation import cache as cache_module
from app.services.test_case_generation.cache import (
    _TEST_CASE_CACHE,
    build_cache_key,
    cache_stats,
    clear_test_case_cache,
    get_cached_result,
    store_cached_result,
)
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
from app.services.test_case_generation.orchestrator import TestCaseEngine


@pytest.fixture(autouse=True)
def clear_cache(monkeypatch):
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
    monkeypatch.delenv("TEST_CASE_CACHE_ENABLED", raising=False)
    monkeypatch.delenv("TEST_CASE_CACHE_TTL_SECONDS", raising=False)
    monkeypatch.delenv("TEST_CASE_CACHE_MAX_ENTRIES", raising=False)
    clear_test_case_cache()
    yield
    clear_test_case_cache()


def raw_requirement(requirement_id="REQ_1", text=None, classification_type="FR"):
    return {
        "id": requirement_id,
        "requirement": text or f"The system shall process record {requirement_id}.",
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


def result_for(requirement=None, status="SUCCESS"):
    requirement = requirement or requirement_model()
    return ResultModel(
        status=status,
        results=[bundle_for(requirement, status="SUCCESS" if status != "PROVIDER_FAILED" else "PROVIDER_FAILED")],
        plans=[plan_for(requirement)],
        warnings=[],
        budget=GenerationBudget(
            mode="mvp_fast",
            estimated_calls=2,
            estimated_tokens=1200,
            calls_used=2,
        ),
    )


def install_fake_pipeline(monkeypatch, calls):
    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        calls["planner"] += 1
        return {requirement.id: plan_for(requirement) for requirement in requirements}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        calls["generator"] += 1
        return {requirement.id: bundle_for(requirement) for requirement in requirements}

    monkeypatch.setattr(
        "app.services.test_case_generation.orchestrator.plan_batch",
        fake_plan_batch,
    )
    monkeypatch.setattr(
        "app.services.test_case_generation.orchestrator.generate_batch",
        fake_generate_batch,
    )


def test_build_cache_key_is_stable_for_same_normalized_input():
    req = requirement_model()

    assert build_cache_key([req], "ctx", "mvp_fast") == build_cache_key([req], "ctx", "mvp_fast")


def test_build_cache_key_changes_when_requirement_text_changes():
    req1 = requirement_model(raw_requirement(text="The system shall export records."))
    req2 = requirement_model(raw_requirement(text="The system shall archive records."))

    assert build_cache_key([req1], "ctx", "mvp_fast") != build_cache_key([req2], "ctx", "mvp_fast")


def test_build_cache_key_changes_when_project_context_changes():
    req = requirement_model()

    assert build_cache_key([req], "ctx1", "mvp_fast") != build_cache_key([req], "ctx2", "mvp_fast")


def test_build_cache_key_changes_when_mode_changes():
    req = requirement_model()

    assert build_cache_key([req], "ctx", "mvp_fast") != build_cache_key([req], "ctx", "balanced")


def test_build_cache_key_includes_prompt_versions(monkeypatch):
    req = requirement_model()
    before = build_cache_key([req], "ctx", "mvp_fast")

    monkeypatch.setattr(cache_module, "TEST_CASE_PROMPT_VERSION", "planner_changed")

    assert before != build_cache_key([req], "ctx", "mvp_fast")


def test_get_cached_result_returns_none_when_cache_empty():
    assert get_cached_result("missing") is None


def test_store_then_get_cached_result_returns_equivalent_result():
    req = requirement_model()
    key = build_cache_key([req], None, "mvp_fast")

    store_cached_result(key, result_for(req))
    cached = get_cached_result(key)

    assert cached is not None
    assert cached.to_dict() == result_for(req).to_dict()


def test_cached_result_is_deep_copied():
    req = requirement_model()
    key = build_cache_key([req], None, "mvp_fast")
    store_cached_result(key, result_for(req))

    cached = get_cached_result(key)
    cached.results[0].status = "NEEDS_REVIEW"

    assert get_cached_result(key).results[0].status == "SUCCESS"


def test_expired_cache_entry_returns_none(monkeypatch):
    req = requirement_model()
    key = build_cache_key([req], None, "mvp_fast")
    store_cached_result(key, result_for(req))
    _TEST_CASE_CACHE[key].created_at = time.time() - 10
    monkeypatch.setenv("TEST_CASE_CACHE_TTL_SECONDS", "1")

    assert get_cached_result(key) is None


def test_cache_max_entries_evicts_oldest(monkeypatch):
    monkeypatch.setenv("TEST_CASE_CACHE_MAX_ENTRIES", "1")
    req1 = requirement_model(raw_requirement("REQ_1"))
    req2 = requirement_model(raw_requirement("REQ_2"))
    key1 = build_cache_key([req1], None, "mvp_fast")
    key2 = build_cache_key([req2], None, "mvp_fast")

    store_cached_result(key1, result_for(req1))
    _TEST_CASE_CACHE[key1].created_at = time.time() - 10
    store_cached_result(key2, result_for(req2))

    assert get_cached_result(key1) is None
    assert get_cached_result(key2) is not None


def test_provider_failed_result_is_not_cached():
    req = requirement_model()
    key = build_cache_key([req], None, "mvp_fast")

    store_cached_result(key, result_for(req, status="PROVIDER_FAILED"))

    assert get_cached_result(key) is None


def test_rate_limited_result_is_not_cached():
    req = requirement_model()
    key = build_cache_key([req], None, "mvp_fast")
    result = result_for(req)
    result.status = "RATE_LIMITED"

    store_cached_result(key, result)

    assert get_cached_result(key) is None


def test_clear_test_case_cache_clears_cache():
    req = requirement_model()
    key = build_cache_key([req], None, "mvp_fast")
    store_cached_result(key, result_for(req))

    clear_test_case_cache()

    assert cache_stats()["size"] == 0


def test_cache_stats_returns_enabled_size_ttl_max_entries():
    stats = cache_stats()

    assert set(stats) == {"enabled", "size", "ttl_seconds", "max_entries"}


def test_first_generate_call_uses_planner_and_generator(monkeypatch):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)

    asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert calls == {"planner": 1, "generator": 1}


def test_second_identical_generate_call_hits_cache(monkeypatch):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)
    engine = TestCaseEngine()

    asyncio.run(engine.generate([raw_requirement()]))
    asyncio.run(engine.generate([raw_requirement()]))

    assert calls == {"planner": 1, "generator": 1}


def test_cache_hit_result_has_calls_used_zero(monkeypatch):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)
    engine = TestCaseEngine()

    asyncio.run(engine.generate([raw_requirement()]))
    cached = asyncio.run(engine.generate([raw_requirement()]))

    assert cached.budget.calls_used == 0


def test_cache_hit_result_includes_warning(monkeypatch):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)
    engine = TestCaseEngine()

    asyncio.run(engine.generate([raw_requirement()]))
    cached = asyncio.run(engine.generate([raw_requirement()]))

    assert "Served from test case generation cache" in cached.warnings


def test_different_project_context_causes_cache_miss(monkeypatch):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)
    engine = TestCaseEngine()

    asyncio.run(engine.generate([raw_requirement()], project_context="a"))
    asyncio.run(engine.generate([raw_requirement()], project_context="b"))

    assert calls == {"planner": 2, "generator": 2}


def test_different_mode_causes_cache_miss(monkeypatch):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)
    engine = TestCaseEngine()

    asyncio.run(engine.generate([raw_requirement()], mode="mvp_fast"))
    asyncio.run(engine.generate([raw_requirement()], mode="balanced"))

    assert calls == {"planner": 2, "generator": 2}


def test_invalid_raw_input_is_not_cached(monkeypatch):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)
    engine = TestCaseEngine()

    asyncio.run(engine.generate([{"id": "REQ_1"}]))

    assert cache_stats()["size"] == 0


def test_cache_disabled_causes_pipeline_to_run_again(monkeypatch):
    monkeypatch.setenv("TEST_CASE_CACHE_ENABLED", "false")
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)
    engine = TestCaseEngine()

    asyncio.run(engine.generate([raw_requirement()]))
    asyncio.run(engine.generate([raw_requirement()]))

    assert calls == {"planner": 2, "generator": 2}


def test_request_start_log_includes_marker(monkeypatch, caplog):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)

    with caplog.at_level(logging.INFO):
        asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert "event=TEST_CASE_REQUEST_START" in caplog.text


def test_cache_hit_log_includes_cache_hit(monkeypatch, caplog):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)
    engine = TestCaseEngine()

    asyncio.run(engine.generate([raw_requirement()]))
    with caplog.at_level(logging.INFO):
        asyncio.run(engine.generate([raw_requirement()]))

    assert "event=CACHE_HIT" in caplog.text


def test_cache_miss_log_includes_cache_miss(monkeypatch, caplog):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)

    with caplog.at_level(logging.INFO):
        asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert "event=CACHE_MISS" in caplog.text


def test_chunk_log_includes_counts(monkeypatch, caplog):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)

    with caplog.at_level(logging.INFO):
        asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert "event=TEST_CASE_CHUNK" in caplog.text
    assert "chunk_index=1" in caplog.text
    assert "safe_count=1" in caplog.text
    assert "blocked_count=0" in caplog.text


def test_requirement_result_log_includes_status_and_count(monkeypatch, caplog):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)

    with caplog.at_level(logging.INFO):
        asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert "event=TEST_CASE_REQUIREMENT_RESULT" in caplog.text
    assert "requirement_id=REQ_1" in caplog.text
    assert "status=SUCCESS" in caplog.text
    assert "test_case_count=1" in caplog.text


def test_request_complete_log_includes_summary(monkeypatch, caplog):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)

    with caplog.at_level(logging.INFO):
        asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert "event=TEST_CASE_REQUEST_COMPLETE" in caplog.text
    assert "final_status=SUCCESS" in caplog.text
    assert "calls_used=3" in caplog.text
    assert "estimated_tokens=" in caplog.text
    assert "cache_hit=False" in caplog.text


def test_logs_do_not_include_full_requirement_text(monkeypatch, caplog):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)

    with caplog.at_level(logging.INFO):
        asyncio.run(TestCaseEngine().generate([raw_requirement(text="Sensitive full text.")]))

    assert "Sensitive full text." not in caplog.text


def test_no_llm_call_on_cache_hit(monkeypatch):
    calls = {"planner": 0, "generator": 0}
    install_fake_pipeline(monkeypatch, calls)
    engine = TestCaseEngine()

    asyncio.run(engine.generate([raw_requirement()]))

    async def fail_plan_batch(*args, **kwargs):
        raise AssertionError("planner should not run")

    async def fail_generate_batch(*args, **kwargs):
        raise AssertionError("generator should not run")

    monkeypatch.setattr(
        "app.services.test_case_generation.orchestrator.plan_batch",
        fail_plan_batch,
    )
    monkeypatch.setattr(
        "app.services.test_case_generation.orchestrator.generate_batch",
        fail_generate_batch,
    )

    cached = asyncio.run(engine.generate([raw_requirement()]))

    assert cached.budget.calls_used == 0


def test_no_text_content_inspection_exists_in_phase10_files():
    combined = "\n".join(
        Path(path).read_text()
        for path in [
            "app/services/test_case_generation/cache.py",
            "app/services/test_case_generation/orchestrator.py",
            "app/services/test_case_generation/logging_utils.py",
        ]
    )

    forbidden = "requirement" + ".lower("
    assert forbidden not in combined

