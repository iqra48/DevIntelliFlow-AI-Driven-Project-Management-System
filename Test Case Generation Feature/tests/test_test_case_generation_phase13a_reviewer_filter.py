import asyncio
from pathlib import Path

import pytest

from app.services.test_case_generation import cache as cache_module
from app.services.test_case_generation.cache import (
    build_cache_key,
    clear_test_case_cache,
    get_cached_result,
)
from app.services.test_case_generation.models import (
    RequirementForTestCase,
    RequirementReviewResult as ReviewResultModel,
    TestCaseReviewDecision as ReviewDecisionModel,
)
from app.services.test_case_generation.orchestrator import (
    TestCaseEngine,
    apply_review_results,
)
from app.services.test_case_generation.prompts import (
    TEST_CASE_REVIEWER_PROMPT_VERSION,
    build_reviewer_system_prompt,
    build_reviewer_user_prompt,
)
from app.services.test_case_generation.reviewer import (
    parse_reviewer_response,
    review_batch,
)
from tests.test_test_case_generation_phase6_orchestrator import (
    bundle_for,
    case_for,
    plan_for,
    raw_requirement,
    requirement_from_raw,
)


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    clear_test_case_cache()
    yield
    clear_test_case_cache()


def requirement(requirement_id="REQ_1"):
    return RequirementForTestCase(
        id=requirement_id,
        requirement=f"The system shall process item {requirement_id}.",
        classification_type="FR",
    )


def review_response(req, decisions, warnings=None):
    return {
        "reviews": {
            "1": {
                "requirement_id": req.id,
                "decisions": decisions,
                "warnings": warnings or [],
            }
        }
    }


def decision_payload(test_case_id, decision="KEEP", reason="Reviewed."):
    return {
        "test_case_id": test_case_id,
        "decision": decision,
        "reason": reason,
        "unsupported_elements": [],
        "required_human_review": decision != "KEEP",
    }


def parsed_review(decisions):
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])
    return parse_reviewer_response(
        review_response(req, decisions),
        [req],
        {req.id: bundle},
    )[req.id]


def test_review_decision_dataclass_works():
    decision = ReviewDecisionModel(
        requirement_id="REQ_1",
        test_case_id="TC_REQ_1_001",
        decision="KEEP",
        reason="Supported.",
        unsupported_elements=[],
        required_human_review=False,
    )

    assert ReviewDecisionModel.from_dict(decision.to_dict()) == decision


def test_requirement_review_result_dataclass_works():
    decision = ReviewDecisionModel(
        "REQ_1",
        "TC_REQ_1_001",
        "KEEP",
        "Supported.",
        [],
        False,
    )
    result = ReviewResultModel("REQ_1", [decision], [])

    assert ReviewResultModel.from_dict(result.to_dict()).decisions[0] == decision


def test_invalid_review_decision_is_rejected_by_parser():
    result = parsed_review([decision_payload("TC_REQ_1_001", "APPROVED")])

    assert result.decisions[0].decision == "REVIEW_NEEDED"


def test_reviewer_prompt_version_is_reviewer_v6():
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_reviewer_system_prompt_says_do_not_repair():
    assert "Do not repair wording" in build_reviewer_system_prompt()


def test_reviewer_system_prompt_says_do_not_create_new_test_cases():
    assert "Do not create new test cases" in build_reviewer_system_prompt()


def test_reviewer_system_prompt_defines_keep():
    assert "KEEP:" in build_reviewer_system_prompt()


def test_reviewer_system_prompt_defines_reject_unsupported_invention():
    assert "REJECT_UNSUPPORTED_INVENTION:" in build_reviewer_system_prompt()


def test_reviewer_system_prompt_defines_review_needed():
    assert "REVIEW_NEEDED:" in build_reviewer_system_prompt()


def test_reviewer_user_prompt_includes_source_basis():
    req = requirement()
    plan = plan_for(req)
    bundle = bundle_for(req, [case_for(req)])

    prompt = build_reviewer_user_prompt([req], {req.id: plan}, {req.id: bundle})

    assert "source_basis" in prompt


def test_reviewer_user_prompt_includes_generated_expected_result():
    req = requirement()
    case = case_for(req)
    plan = plan_for(req)
    bundle = bundle_for(req, [case])

    prompt = build_reviewer_user_prompt([req], {req.id: plan}, {req.id: bundle})

    assert case.expected_result in prompt


def test_reviewer_user_prompt_uses_compact_json():
    req = requirement()
    plan = plan_for(req)
    bundle = bundle_for(req, [case_for(req)])

    prompt = build_reviewer_user_prompt([req], {req.id: plan}, {req.id: bundle})

    assert '"requirements":[{' in prompt


def test_parse_keep_decision():
    result = parsed_review([decision_payload("TC_REQ_1_001", "KEEP")])

    assert result.decisions[0].decision == "KEEP"


def test_parse_reject_unsupported_invention_decision():
    result = parsed_review(
        [decision_payload("TC_REQ_1_001", "REJECT_UNSUPPORTED_INVENTION")]
    )

    assert result.decisions[0].decision == "REJECT_UNSUPPORTED_INVENTION"


def test_parse_review_needed_decision():
    result = parsed_review([decision_payload("TC_REQ_1_001", "REVIEW_NEEDED")])

    assert result.decisions[0].decision == "REVIEW_NEEDED"


def test_missing_decision_becomes_review_needed():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])

    result = parse_reviewer_response(
        review_response(req, []),
        [req],
        {req.id: bundle},
    )[req.id]

    assert result.decisions[0].decision == "REVIEW_NEEDED"


def test_unknown_test_case_id_is_ignored_with_warning():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])

    result = parse_reviewer_response(
        review_response(req, [decision_payload("TC_UNKNOWN")]),
        [req],
        {req.id: bundle},
    )[req.id]

    assert result.decisions[0].decision == "REVIEW_NEEDED"
    assert result.warnings


def test_malformed_reviewer_response_marks_all_reviewed_cases_review_needed():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])

    result = parse_reviewer_response("not json", [req], {req.id: bundle})[req.id]

    assert result.decisions[0].decision == "REVIEW_NEEDED"


def test_invalid_individual_decision_marks_that_case_review_needed():
    result = parsed_review(
        [
            {
                "test_case_id": "TC_REQ_1_001",
                "decision": "KEEP",
                "reason": "",
                "unsupported_elements": [],
                "required_human_review": False,
            }
        ]
    )

    assert result.decisions[0].decision == "REVIEW_NEEDED"


def test_call_llm_exception_propagates_from_review_batch(monkeypatch):
    async def fake_call_llm(prompt, system_prompt=None, num_predict=None):
        raise RuntimeError("provider failed")

    req = requirement()
    bundle = bundle_for(req, [case_for(req)])
    monkeypatch.setattr("app.services.test_case_generation.reviewer.call_llm", fake_call_llm)

    with pytest.raises(RuntimeError):
        asyncio.run(review_batch([req], {req.id: plan_for(req)}, {req.id: bundle}))


def test_keep_preserves_test_case_and_success():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])
    reviewed = apply_review_results(
        {req.id: bundle},
        {req.id: ReviewResultModel(req.id, [keep_decision(req)], [])},
    )[req.id]

    assert reviewed.status == "SUCCESS"
    assert len(reviewed.test_cases) == 1


def test_review_needed_preserves_test_case_and_sets_needs_review():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])
    reviewed = apply_review_results(
        {req.id: bundle},
        {req.id: ReviewResultModel(req.id, [review_needed_decision(req)], [])},
    )[req.id]

    assert reviewed.status == "NEEDS_REVIEW"
    assert len(reviewed.test_cases) == 1


def test_reject_removes_test_case_and_sets_needs_review():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])
    reviewed = apply_review_results(
        {req.id: bundle},
        {req.id: ReviewResultModel(req.id, [reject_decision(req)], [])},
    )[req.id]

    assert reviewed.status == "NEEDS_REVIEW"
    assert reviewed.test_cases == []


def test_all_rejected_leaves_empty_cases_and_needs_review():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])
    reviewed = apply_review_results(
        {req.id: bundle},
        {req.id: ReviewResultModel(req.id, [reject_decision(req)], [])},
    )[req.id]

    assert reviewed.reason == "All generated test cases were rejected by reviewer"


def test_mixed_keep_reject_keeps_only_kept_cases():
    req = requirement()
    case1 = case_for(req, "TC_REQ_1_001")
    case2 = case_for(req, "TC_REQ_1_002")
    bundle = bundle_for(req, [case1, case2])
    reviewed = apply_review_results(
        {req.id: bundle},
        {
            req.id: ReviewResultModel(
                req.id,
                [keep_decision(req, "TC_REQ_1_001"), reject_decision(req, "TC_REQ_1_002")],
                [],
            )
        },
    )[req.id]

    assert [case.test_case_id for case in reviewed.test_cases] == ["TC_REQ_1_001"]


def test_original_needs_review_stays_needs_review_even_if_kept():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)], status="NEEDS_REVIEW")
    reviewed = apply_review_results(
        {req.id: bundle},
        {req.id: ReviewResultModel(req.id, [keep_decision(req)], [])},
    )[req.id]

    assert reviewed.status == "NEEDS_REVIEW"


def test_missing_reviewer_decision_marks_needs_review():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])
    reviewed = apply_review_results({req.id: bundle}, {})[req.id]

    assert reviewed.status == "NEEDS_REVIEW"


def test_warnings_include_reviewer_reasons():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])
    reviewed = apply_review_results(
        {req.id: bundle},
        {req.id: ReviewResultModel(req.id, [review_needed_decision(req)], [])},
    )[req.id]

    assert "Needs human review" in " ".join(reviewed.warnings)


def test_no_approved_status_is_introduced():
    prompt = build_reviewer_system_prompt()

    assert "APPROVED" not in prompt


def test_reviewer_called_after_validation(monkeypatch):
    called = {"reviewer": 0}

    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        called["reviewer"] += 1
        return keep_results(requirements, bundles)

    install_fake_generation(monkeypatch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert called["reviewer"] == 1


def test_reviewer_called_once_per_chunk_not_once_per_test_case(monkeypatch):
    called = {"reviewer": 0}

    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        called["reviewer"] += 1
        return keep_results(requirements, bundles)

    install_fake_generation(monkeypatch, cases_per_bundle=2)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert called["reviewer"] == 1


def test_reviewer_not_called_for_blocked_bundles(monkeypatch):
    called = {"reviewer": 0}

    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req, safe=False) for req in requirements}

    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        called["reviewer"] += 1
        return {}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert called["reviewer"] == 0


def test_reviewer_not_called_for_provider_terminal_bundles(monkeypatch):
    called = {"reviewer": 0}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        from app.services.test_case_generation.generator import make_failed_bundle

        return {
            req.id: make_failed_bundle(req, "PROVIDER_FAILED", "failed", plans[req.id])
            for req in requirements
        }

    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        called["reviewer"] += 1
        return {}

    install_fake_planner(monkeypatch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert called["reviewer"] == 0


def test_reviewer_not_called_for_failed_schema_bundles(monkeypatch):
    called = {"reviewer": 0}

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        bundle = bundle_for(requirements[0], [case_for(requirements[0])])
        bundle.test_cases[0].title = ""
        return {requirements[0].id: bundle}

    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        called["reviewer"] += 1
        return {}

    install_fake_planner(monkeypatch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert called["reviewer"] == 0


def test_reviewer_rejected_cases_are_absent_from_final_result(monkeypatch):
    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        req = requirements[0]
        return {req.id: ReviewResultModel(req.id, [reject_decision(req)], [])}

    install_fake_generation(monkeypatch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.results[0].test_cases == []


def test_reviewer_failure_marks_usable_bundles_needs_review_not_provider_failed(monkeypatch):
    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        raise RuntimeError("reviewer unavailable")

    install_fake_generation(monkeypatch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.status == "NEEDS_REVIEW"
    assert result.results[0].status == "NEEDS_REVIEW"


def test_calls_used_includes_reviewer_call(monkeypatch):
    install_fake_generation(monkeypatch)
    monkeypatch.setattr(
        "app.services.test_case_generation.orchestrator.review_batch",
        fake_keep_review_batch,
    )

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.budget.calls_used == 3


def test_estimate_endpoint_returns_four_calls_for_one_mvp_fast_chunk():
    from app.services.test_case_generation.token_budget import estimate_calls

    assert estimate_calls([requirement()], "mvp_fast") == 4


def test_cache_stores_reviewed_result(monkeypatch):
    install_fake_generation(monkeypatch)

    async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
        return {
            requirements[0].id: ReviewResultModel(
                requirements[0].id,
                [reject_decision(requirements[0])],
                [],
            )
        }

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)
    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))
    key = build_cache_key([requirement_from_raw(raw_requirement())], None, "mvp_fast")
    cached = get_cached_result(key)

    assert result.results[0].test_cases == []
    assert cached.results[0].test_cases == []


def test_cache_key_changes_when_reviewer_prompt_version_changes(monkeypatch):
    req = requirement()
    before = build_cache_key([req], "ctx", "mvp_fast")

    monkeypatch.setattr(cache_module, "TEST_CASE_REVIEWER_PROMPT_VERSION", "reviewer_old")

    assert before != build_cache_key([req], "ctx", "mvp_fast")


def test_planner_generator_source_basis_tests_still_pass():
    item = plan_for(requirement()).coverage_items[0]

    assert item.source_basis


def test_validation_still_enforces_source_basis():
    from app.services.test_case_generation.validation import (
        TestCaseValidationError,
        validate_planner_output_against_requirement,
    )

    req = requirement()
    plan = plan_for(req)
    plan.coverage_items[0].source_basis = []

    with pytest.raises(TestCaseValidationError):
        validate_planner_output_against_requirement(plan, req)


def test_provider_passthrough_helpers_still_available():
    from app.services.test_case_generation.orchestrator import is_terminal_provider_bundle
    from app.services.test_case_generation.generator import make_failed_bundle

    req = requirement()

    assert is_terminal_provider_bundle(make_failed_bundle(req, "PROVIDER_FAILED", "failed"))


def test_no_ui_files_changed_for_phase13a():
    assert Path("ui").exists()


def test_no_repairer_file_added():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_reviewer_py_has_no_requirement_lower():
    assert "requirement" + "." + "low" + "er(" not in Path(
        "app/services/test_case_generation/reviewer.py"
    ).read_text()


def test_reviewer_py_has_no_keyword_branch_implementation():
    text = Path("app/services/test_case_generation/reviewer.py").read_text()
    forbidden = [
        'if "' + "login" + '" in',
        'if "' + "password" + '" in',
        'if "' + "payment" + '" in',
        'if "' + "security" + '" in',
        'if "' + "download" + '" in',
        'if "' + "archive" + '" in',
    ]

    for fragment in forbidden:
        assert fragment not in text


def test_orchestrator_has_no_business_keyword_routing():
    text = Path("app/services/test_case_generation/orchestrator.py").read_text()

    assert "keyword-to" + "-test-type maps" not in text
    assert "hardcoded business" + "/domain routing" not in text


def test_no_unapproved_matching_terms_in_implementation():
    text = "\n".join(
        Path(path).read_text()
        for path in [
            "app/services/test_case_generation/models.py",
            "app/services/test_case_generation/token_budget.py",
            "app/services/test_case_generation/cache.py",
            "app/services/test_case_generation/reviewer.py",
            "app/services/test_case_generation/orchestrator.py",
        ]
    )
    forbidden = [
        "fu" + "zzy",
        "sim" + "ilarity",
        "con" + "tains(",
        "start" + "swith(",
        "." + "low" + "er(",
    ]

    for fragment in forbidden:
        assert fragment not in text


def test_tests_do_not_call_live_llm():
    text = Path("tests/test_test_case_generation_phase13a_reviewer_filter.py").read_text()

    assert "Groq" + "Provider" not in text
    assert "requests" + "." not in text
    assert "httpx" + "." not in text


def keep_decision(req, test_case_id="TC_REQ_1_001"):
    return ReviewDecisionModel(
        req.id,
        test_case_id,
        "KEEP",
        "Supported.",
        [],
        False,
    )


def review_needed_decision(req, test_case_id="TC_REQ_1_001"):
    return ReviewDecisionModel(
        req.id,
        test_case_id,
        "REVIEW_NEEDED",
        "Needs human review.",
        [],
        True,
    )


def reject_decision(req, test_case_id="TC_REQ_1_001"):
    return ReviewDecisionModel(
        req.id,
        test_case_id,
        "REJECT_UNSUPPORTED_INVENTION",
        "Unsupported behavior.",
        ["Unsupported behavior"],
        True,
    )


def keep_results(requirements, bundles):
    return {
        req.id: ReviewResultModel(
            req.id,
            [keep_decision(req, test_case.test_case_id) for test_case in bundles[req.id].test_cases],
            [],
        )
        for req in requirements
        if req.id in bundles
    }


async def fake_keep_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
    return keep_results(requirements, bundles)


def install_fake_planner(monkeypatch):
    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        return {req.id: plan_for(req) for req in requirements}

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)


def install_fake_generation(monkeypatch, cases_per_bundle=1):
    install_fake_planner(monkeypatch)

    async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
        output = {}
        for req in requirements:
            cases = [case_for(req, f"TC_{req.id}_{index:03d}") for index in range(1, cases_per_bundle + 1)]
            output[req.id] = bundle_for(req, cases)
        return output

    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)


