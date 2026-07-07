from pathlib import Path

from app.services.test_case_generation import cache as cache_module
from app.services.test_case_generation.cache import build_cache_key
from app.services.test_case_generation.models import (
    RequirementForTestCase,
    RequirementReviewResult,
    TestCaseReviewDecision,
)
from app.services.test_case_generation.orchestrator import apply_review_results
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
    build_generator_system_prompt,
    build_generator_user_prompt,
    build_reviewer_system_prompt,
)
from tests.test_test_case_generation_phase6_orchestrator import (
    bundle_for,
    case_for,
    plan_for,
)


IMPLEMENTATION_FILES = [
    Path("app/services/test_case_generation/cache.py"),
    Path("app/services/test_case_generation/orchestrator.py"),
    Path("app/services/test_case_generation/reviewer.py"),
]


def requirement(requirement_id="REQ_1"):
    return RequirementForTestCase(
        id=requirement_id,
        requirement=f"The system shall process item {requirement_id}.",
        classification_type="FR",
    )


def review_result(requirement_id, test_case_id, decision, reason="Reviewed."):
    return RequirementReviewResult(
        requirement_id=requirement_id,
        decisions=[
            TestCaseReviewDecision(
                requirement_id=requirement_id,
                test_case_id=test_case_id,
                decision=decision,
                reason=reason,
                unsupported_elements=[],
                required_human_review=decision != "KEEP",
            )
        ],
        warnings=[],
    )


def reviewed_bundle(decision, reason="Reviewed."):
    req = requirement()
    test_case = case_for(req)
    bundle = bundle_for(req, [test_case])
    result = review_result(req.id, test_case.test_case_id, decision, reason)
    return apply_review_results({req.id: bundle}, {req.id: result})[req.id]


def test_generator_prompt_version_is_generator_v8():
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"


def test_reviewer_prompt_version_is_reviewer_v6():
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_generator_prompt_has_implementation_neutral_section():
    assert "IMPLEMENTATION-NEUTRAL TEST CASES" in build_generator_system_prompt()


def test_generator_prompt_requires_requirement_level_not_ui_level_cases():
    prompt = build_generator_system_prompt()

    assert "requirement-level test cases" in prompt
    assert "not UI-level or architecture-level" in prompt


def test_generator_prompt_forbids_invented_implementation_surfaces():
    prompt = build_generator_system_prompt()

    assert "pages, screens, forms, fields, buttons, links" in prompt
    assert "API endpoints" in prompt
    assert "database details" in prompt


def test_generator_prompt_forbids_access_setup_auth_and_exact_messages():
    prompt = build_generator_system_prompt()

    assert "exact messages" in prompt
    assert "permissions" in prompt
    assert "authentication state" in prompt
    assert "access setup" in prompt


def test_generator_prompt_requires_generic_configured_wording_for_missing_details():
    prompt = build_generator_system_prompt()

    assert "use generic configured wording" in prompt
    assert "set assumption_required=true" in prompt


def test_generator_prompt_forbids_concrete_ui_verbs_unless_stated():
    prompt = build_generator_system_prompt()

    assert "concrete UI verbs" in prompt
    assert "unless those interactions are explicitly stated" in prompt


def test_generator_prompt_forbids_invented_test_data_and_access_setup():
    prompt = build_generator_system_prompt()

    assert "Do not invent concrete test data fields" in prompt
    assert "access grants" in prompt
    assert "configured access" in prompt


def test_generator_prompt_preconditions_must_stay_implementation_neutral():
    prompt = build_generator_system_prompt()

    assert "Preconditions must stay implementation-neutral" in prompt
    assert "Do not mention logged-in users" in prompt
    assert "configured prerequisites are available" in prompt


def test_generator_prompt_validation_uses_configured_rejection_outcome():
    prompt = build_generator_system_prompt()

    assert "configured rejection outcome" in prompt
    assert "validation feedback" in prompt


def test_generator_prompt_simple_requirements_prefer_one_main_path():
    prompt = build_generator_system_prompt()

    assert "prefer one main-path test" in prompt
    assert "planner coverage supplies" in prompt


def test_generator_prompt_nfrs_must_not_invent_measurement_details():
    prompt = build_generator_system_prompt()

    assert "For NFRs" in prompt
    assert "do not invent partitions, tools" in prompt
    assert "thresholds" in prompt


def test_generator_prompt_vague_requirements_return_no_tautology():
    prompt = build_generator_system_prompt()

    assert "return no test case" in prompt
    assert "tautological" in prompt


def test_generator_user_prompt_adds_implementation_neutral_reminder():
    req = requirement()
    prompt = build_generator_user_prompt([req], {req.id: plan_for(req)})

    assert "Use implementation-neutral wording" in prompt
    assert "Do not invent UI/access/setup details" in prompt
    assert "set assumption_required=true" in prompt


def test_reviewer_prompt_has_strict_implementation_invention_section():
    assert "STRICT IMPLEMENTATION-INVENTION REVIEW" in build_reviewer_system_prompt()


def test_reviewer_prompt_rejects_unsupported_concrete_details():
    prompt = build_reviewer_system_prompt()

    assert "Reject unsupported concrete implementation details" in prompt
    assert "pages, screens" in prompt
    assert "exact messages" in prompt


def test_reviewer_prompt_rejects_auth_and_permission_assumptions():
    prompt = build_reviewer_system_prompt()

    assert "Reject login, authentication, authorization" in prompt
    assert "permission, or role assumptions" in prompt


def test_reviewer_prompt_rejects_invented_test_data_and_access_setup():
    prompt = build_reviewer_system_prompt()

    assert "Reject invented concrete test data fields" in prompt
    assert "user accounts" in prompt
    assert "setup paths" in prompt


def test_reviewer_prompt_reviews_all_fields_and_rejects_precondition_invention():
    prompt = build_reviewer_system_prompt()

    assert "Review every field" in prompt
    assert "Unsupported invention in any field is enough to reject" in prompt
    assert "Reject unsupported preconditions" in prompt
    assert "Do not keep a case just because its main objective is valid" in prompt


def test_reviewer_prompt_rejects_specific_ui_mechanics():
    prompt = build_reviewer_system_prompt()

    assert "specific UI mechanics" in prompt
    assert "click, navigate" in prompt


def test_reviewer_prompt_rejects_extra_behavior_not_in_coverage():
    prompt = build_reviewer_system_prompt()

    assert "extra invalid, edge, alternate" in prompt
    assert "not present in planner coverage and source_basis" in prompt


def test_reviewer_prompt_uses_review_needed_for_missing_detail():
    prompt = build_reviewer_system_prompt()

    assert "Use REVIEW_NEEDED when measurement details" in prompt
    assert "not clearly invented behavior" in prompt


def test_reviewer_prompt_keep_only_generic_or_directly_supported_cases():
    prompt = build_reviewer_system_prompt()

    assert "Keep only cases that are generic or directly supported" in prompt
    assert "Every remaining test case must be independently source-supported" in prompt


def test_reject_unsupported_invention_removes_ui_specific_case():
    bundle = reviewed_bundle(
        "REJECT_UNSUPPORTED_INVENTION",
        "Unsupported specific page and button.",
    )

    assert bundle.status == "NEEDS_REVIEW"
    assert bundle.test_cases == []
    assert any("Unsupported specific page and button." in item for item in bundle.warnings)


def test_keep_preserves_implementation_neutral_case():
    bundle = reviewed_bundle("KEEP", "Generic wording is supported.")

    assert bundle.status == "SUCCESS"
    assert len(bundle.test_cases) == 1
    assert bundle.warnings == []


def test_review_needed_keeps_case_and_marks_needs_review():
    bundle = reviewed_bundle("REVIEW_NEEDED", "Access detail is missing.")

    assert bundle.status == "NEEDS_REVIEW"
    assert len(bundle.test_cases) == 1
    assert any("Access detail is missing." in item for item in bundle.warnings)


def test_all_rejected_leaves_needs_review_with_empty_test_cases():
    bundle = reviewed_bundle("REJECT_UNSUPPORTED_INVENTION", "Unsupported detail.")

    assert bundle.status == "NEEDS_REVIEW"
    assert bundle.test_cases == []
    assert "All generated test cases were rejected by reviewer" in bundle.warnings


def test_rejection_warning_includes_reviewer_reason():
    bundle = reviewed_bundle("REJECT_UNSUPPORTED_INVENTION", "Reviewer reason here.")

    assert any("Reviewer reason here." in warning for warning in bundle.warnings)


def test_cache_key_changes_when_generator_prompt_version_changes(monkeypatch):
    req = requirement()
    original_key = build_cache_key([req], None, "mvp_fast")

    monkeypatch.setattr(cache_module, "TEST_CASE_GENERATOR_PROMPT_VERSION", "generator_test")

    assert build_cache_key([req], None, "mvp_fast") != original_key


def test_cache_key_changes_when_reviewer_prompt_version_changes(monkeypatch):
    req = requirement()
    original_key = build_cache_key([req], None, "mvp_fast")

    monkeypatch.setattr(cache_module, "TEST_CASE_REVIEWER_PROMPT_VERSION", "reviewer_test")

    assert build_cache_key([req], None, "mvp_fast") != original_key


def test_no_approved_review_decision_added():
    text = Path("app/services/test_case_generation/models.py").read_text(encoding="utf-8")

    assert '"APPROVED"' not in text
    assert "'APPROVED'" not in text


def test_no_repairer_py_added():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_strict_groq_phase_tests_still_exist():
    assert Path("tests/test_test_case_generation_phase13b_groq_only_eval_safety.py").exists()


def test_phase13d_batch_merge_tests_still_exist():
    assert Path("tests/test_test_case_generation_phase13d_batch_merge.py").exists()


def test_no_requirement_lower_in_reviewer_or_orchestrator_or_cache():
    forbidden = "requirement" + ".lower("
    combined = "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES)

    assert forbidden not in combined


def test_no_keyword_branch_implementation_in_reviewer_or_orchestrator_or_cache():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES)
    sensitive_words = [
        "login",
        "password",
        "payment",
        "security",
        "button",
        "page",
    ]

    for word in sensitive_words:
        assert f'if "{word}" in' not in combined
        assert f"if '{word}' in" not in combined


def test_no_fuzzy_similarity_contains_startswith_in_reviewer_or_orchestrator_or_cache():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES)

    assert "fuzzy" not in combined
    assert "similarity" not in combined
    assert "contains(" not in combined
    assert "startswith(" not in combined


def test_no_provider_or_fallback_changes_in_phase13e_prompt_files():
    prompt_text = Path("app/services/test_case_generation/prompts.py").read_text(
        encoding="utf-8"
    )

    assert "Gemini" not in prompt_text
    assert "Cerebras" not in prompt_text
    assert "fallback provider" not in prompt_text


