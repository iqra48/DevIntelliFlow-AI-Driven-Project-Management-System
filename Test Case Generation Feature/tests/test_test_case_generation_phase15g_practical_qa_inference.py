import re
from pathlib import Path

from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
    build_planner_system_prompt,
)


def planner_prompt() -> str:
    return build_planner_system_prompt().casefold()


def test_phase15g_prompt_versions_change_only_planner():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_planner_prompt_contains_practical_qa_inference():
    assert "practical qa inference" in planner_prompt()


def test_planner_prompt_contains_practical_coverage_minimum():
    assert "practical coverage minimum" in planner_prompt()


def test_safe_observable_capability_normally_targets_two_to_three_items():
    prompt = planner_prompt()

    assert "safe, observable user or system capability requirement" in prompt
    assert "normally create" in prompt
    assert "2 to 3 coverage items" in prompt


def test_positive_negative_boundary_are_generic_non_invented_targets():
    prompt = planner_prompt()

    assert "target positive coverage" in prompt
    assert "target negative coverage" in prompt
    assert "target boundary/edge coverage" in prompt
    assert "generic and non-invented" in prompt


def test_single_positive_only_requires_explanation():
    prompt = planner_prompt()

    assert "only one positive coverage item" in prompt
    assert "explaining why" in prompt
    assert "negative and boundary coverage cannot be generated safely" in prompt


def test_same_source_basis_phrase_can_support_generic_inferred_coverage():
    prompt = planner_prompt()

    assert "same exact source_basis phrase may justify" in prompt
    assert "positive, negative, and boundary/edge coverage" in prompt
    assert "establishes the capability being verified" in prompt


def test_planner_allows_generic_invalid_input_when_semantically_necessary():
    prompt = planner_prompt()

    assert "invalid configured input is rejected" in prompt
    assert "semantically necessary to verify the requirement" in prompt


def test_planner_allows_missing_required_information_when_semantically_necessary():
    prompt = planner_prompt()

    assert "missing required information is handled" in prompt
    assert "when semantically necessary" in prompt


def test_planner_keeps_product_specific_anti_invention_guard():
    prompt = planner_prompt()

    for forbidden_detail in [
        "dashboard redirects",
        "otp",
        "account lockout rules",
        "exact error messages",
        "screen",
        "button",
        "form",
        "api",
        "database",
    ]:
        assert forbidden_detail in prompt
    assert "must not invent product-specific details" in prompt


def test_planner_says_practical_inference_is_not_a_fixed_count_rule():
    prompt = planner_prompt()

    assert "semantic qa reasoning, not a fixed count rule" in prompt
    assert "do not force exactly three test cases" in prompt


def test_planner_retains_normal_and_hard_case_count_limits():
    prompt = planner_prompt()

    assert "prefer one to three useful coverage items" in prompt
    assert "hard max: 5" in prompt


def test_phase15g_adds_no_python_keyword_domain_branching():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "app/services/test_case_generation/planner.py",
            "app/services/test_case_generation/generator.py",
            "app/services/test_case_generation/validation.py",
            "app/services/test_case_generation/orchestrator.py",
        ]
    )
    keyword_branch = re.compile(
        r"\bif\s+[\"'](?:login|upload|report|password|dashboard)[\"']\s+in\b",
        re.IGNORECASE,
    )

    assert keyword_branch.search(source) is None


def test_planner_prompt_has_no_approval_or_repairer_contract():
    prompt = planner_prompt()

    assert "approved" not in prompt
    assert "repairer" not in prompt
