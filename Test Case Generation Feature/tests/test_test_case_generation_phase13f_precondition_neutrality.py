from pathlib import Path

from app.services.test_case_generation import cache as cache_module
from app.services.test_case_generation.cache import build_cache_key
from app.services.test_case_generation.models import RequirementForTestCase
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
    build_generator_system_prompt,
    build_reviewer_system_prompt,
)


IMPLEMENTATION_FILES = [
    Path("app/services/test_case_generation/cache.py"),
    Path("app/services/test_case_generation/orchestrator.py"),
    Path("app/services/test_case_generation/reviewer.py"),
]


def requirement():
    return RequirementForTestCase(
        id="REQ_1",
        requirement="The system shall process a requirement.",
        classification_type="FR",
    )


def test_generator_version_is_generator_v8():
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"


def test_reviewer_version_is_reviewer_v6():
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_generator_prompt_contains_precondition_and_test_data_neutrality():
    assert "PRECONDITION AND TEST DATA NEUTRALITY" in build_generator_system_prompt()


def test_generator_prompt_forbids_actor_to_login_session_permission():
    prompt = build_generator_system_prompt()

    assert "If the requirement implies an actor" in prompt
    assert "do not convert the actor into a login/session/permission precondition" in prompt


def test_generator_prompt_allows_source_grounded_state_preconditions():
    prompt = build_generator_system_prompt()

    assert "required object or state is directly stated" in prompt
    assert "Directly stated source-grounded state preconditions are acceptable" in prompt


def test_generator_prompt_requires_generic_configured_prerequisites_when_setup_missing():
    prompt = build_generator_system_prompt()

    assert "Configured prerequisites for exercising this capability are available." in prompt
    assert "If setup is necessary but not specified" in prompt


def test_generator_prompt_requires_assumption_required_true_for_missing_setup():
    prompt = build_generator_system_prompt()

    assert "set assumption_required=true" in prompt
    assert "visible assumptions" in prompt


def test_generator_prompt_forbids_concrete_fake_test_data_unless_stated_or_required():
    prompt = build_generator_system_prompt()

    assert "test_data must not invent names, emails, phone numbers" in prompt
    assert "unless stated or required by an explicit validation boundary" in prompt
    assert "concrete fake values" in prompt
    assert "Do not populate test_data with keys or values" in prompt
    assert "Use empty test_data when fields or exact values are not source-grounded" in prompt
    assert "test_data must be an" in prompt
    assert "empty object unless requirement" in prompt


def test_reviewer_prompt_contains_strict_precondition_and_test_data_review():
    assert "STRICT PRECONDITION AND TEST DATA REVIEW" in build_reviewer_system_prompt()


def test_reviewer_prompt_rejects_unsupported_login_auth_permission_preconditions():
    prompt = build_reviewer_system_prompt()

    assert "Reject a test case if preconditions invent login" in prompt
    assert "authentication" in prompt
    assert "permission" in prompt


def test_reviewer_prompt_rejects_actor_converted_into_logged_in_actor():
    prompt = build_reviewer_system_prompt()

    assert "Reject when an actor in the requirement is turned into logged-in" in prompt
    assert "manager/admin/user" in prompt


def test_reviewer_prompt_rejects_unsupported_concrete_sample_data():
    prompt = build_reviewer_system_prompt()

    assert "Reject concrete sample names, emails, phone numbers" in prompt
    assert "IDs, dates, amounts" in prompt
    assert "unless stated by the requirement" in prompt
    assert "Reject test_data when it contains unsupported keys or values" in prompt
    assert "reject non-empty" in prompt
    assert "source explicitly names the fields" in prompt


def test_reviewer_prompt_keeps_generic_configured_prerequisites_with_assumptions():
    prompt = build_reviewer_system_prompt()

    assert "Keep generic configured prerequisite wording" in prompt
    assert "assumption_required=true" in prompt
    assert "assumptions explain missing setup/access details" in prompt


def test_reviewer_prompt_keeps_directly_source_grounded_state_preconditions():
    prompt = build_reviewer_system_prompt()

    assert "Keep directly source-grounded state preconditions" in prompt
    assert "state explicitly named by the requirement" in prompt


def test_reviewer_prompt_rejects_when_preconditions_or_test_data_are_unsupported():
    prompt = build_reviewer_system_prompt()

    assert "unsupported preconditions/test_data" in prompt
    assert "reject it" in prompt
    assert "Do not keep it only because the objective is valid" in prompt


def test_cache_key_changes_for_generator_v8(monkeypatch):
    req = requirement()
    original_key = build_cache_key([req], None, "mvp_fast")

    monkeypatch.setattr(cache_module, "TEST_CASE_GENERATOR_PROMPT_VERSION", "generator_v8_test")

    assert build_cache_key([req], None, "mvp_fast") != original_key


def test_cache_key_changes_for_reviewer_v6(monkeypatch):
    req = requirement()
    original_key = build_cache_key([req], None, "mvp_fast")

    monkeypatch.setattr(cache_module, "TEST_CASE_REVIEWER_PROMPT_VERSION", "reviewer_v6_test")

    assert build_cache_key([req], None, "mvp_fast") != original_key


def test_no_approved_status_added():
    text = Path("app/services/test_case_generation/models.py").read_text(encoding="utf-8")

    assert '"APPROVED"' not in text
    assert "'APPROVED'" not in text


def test_no_repairer_py_added():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_strict_groq_provider_tests_still_exist():
    assert Path("tests/test_test_case_generation_phase13b_groq_only_eval_safety.py").exists()


def test_no_python_keyword_rule_based_semantic_logic():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES)
    forbidden_fragments = [
        "requirement" + ".lower(",
        ".lower(",
        'if "' + "login" + '" in',
        "if '" + "login" + "' in",
        'if "' + "manager" + '" in',
        "if '" + "manager" + "' in",
        'if "' + "button" + '" in',
        "if '" + "button" + "' in",
        'if "' + "page" + '" in',
        "if '" + "page" + "' in",
        'if "' + "field" + '" in',
        "if '" + "field" + "' in",
        "fuzzy",
        "similarity",
        "contains(",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in combined


