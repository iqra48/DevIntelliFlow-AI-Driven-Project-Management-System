import asyncio
from pathlib import Path

from app.services.test_case_generation.models import (
    ALLOWED_STATUSES,
    RequirementForTestCase,
    TestCase as TestCaseModel,
    TestStep as TestStepModel,
)
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
    build_generator_system_prompt,
    build_planner_system_prompt,
    build_reviewer_system_prompt,
)
from app.services.test_case_generation.reviewer import review_batch
from tests.test_test_case_generation_phase6_orchestrator import (
    bundle_for,
    coverage_item,
    plan_for,
)


PRODUCTION_FILES_TO_SCAN = [
    path
    for path in Path("app/services/test_case_generation").glob("*.py")
    if path.name not in {"prompts.py", "__init__.py"}
] + [
    Path("app/shared/llm/llm_router.py"),
    Path("app/shared/llm/call_llm.py"),
]


def normalized(text: str) -> str:
    return " ".join(text.split())


def requirement(text: str, requirement_id: str = "REQ_1", kind: str = "FR"):
    return RequirementForTestCase(
        id=requirement_id,
        requirement=text,
        classification_type=kind,
    )


def case_with(requirement_obj, **overrides):
    item = coverage_item("Verify stated constraint.")
    payload = {
        "test_case_id": f"TC_{requirement_obj.id}_001",
        "requirement_id": requirement_obj.id,
        "title": "Verify stated constraint",
        "objective": "Verify the stated constraint.",
        "test_type": item.test_type,
        "technique_used": item.technique_used,
        "priority": item.priority,
        "preconditions": ["Configured prerequisites for exercising this capability are available."],
        "test_data": {},
        "steps": [
            TestStepModel(
                step_number=1,
                action="Exercise the configured capability.",
                expected_result="The configured outcome reflects the stated requirement.",
            )
        ],
        "expected_result": "The configured outcome reflects the stated requirement.",
        "assumption_required": True,
        "assumptions": [],
        "source_basis": [requirement_obj.requirement],
        "traceability": {
            "requirement_id": requirement_obj.id,
            "coverage_item": item.coverage_item,
            "technique_used": item.technique_used,
        },
    }
    payload.update(overrides)
    return TestCaseModel(**payload)


async def reviewed_decision_for(monkeypatch, requirement_obj, test_case, unsupported_element):
    async def fake_call_llm(**kwargs):
        return {
            "reviews": {
                "1": {
                    "requirement_id": requirement_obj.id,
                    "decisions": [
                        {
                            "requirement_id": requirement_obj.id,
                            "test_case_id": test_case.test_case_id,
                            "decision": "REJECT_UNSUPPORTED_INVENTION",
                            "reason": f"Unsupported invention: {unsupported_element}",
                            "unsupported_elements": [unsupported_element],
                            "required_human_review": True,
                        }
                    ],
                    "warnings": [],
                }
            }
        }

    monkeypatch.setattr("app.services.test_case_generation.reviewer.call_llm", fake_call_llm)
    plan = plan_for(requirement_obj)
    bundle = bundle_for(requirement_obj, [test_case])
    reviews = await review_batch(
        [requirement_obj],
        {requirement_obj.id: plan},
        {requirement_obj.id: bundle},
    )
    return reviews[requirement_obj.id].decisions[0]


def test_prompt_versions_are_phase15d_versions():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_planner_prompt_contains_constraint_only_requirements():
    assert "CONSTRAINT-ONLY REQUIREMENTS" in build_planner_system_prompt()


def test_planner_required_reason_is_constraint_not_ui_mechanism():
    prompt = normalized(build_planner_system_prompt())

    assert "A required field/reason requirement supports verification" in prompt
    assert "does not support inventing the UI mechanism" in prompt
    assert "prompt, dialog, form, page, screen, field widget" in prompt
    assert "must say the system enforces the required information" in prompt
    assert "Do not say the system prompts for, asks for, displays, captures, accepts" in prompt
    assert 'Do not create a positive "provided value succeeds/proceeds" workflow' in prompt


def test_planner_one_time_code_does_not_imply_authentication_completion():
    prompt = normalized(build_planner_system_prompt())

    assert "one-time-code entry requirement" in prompt
    assert "does not imply authentication completion" in prompt
    assert "must say code entry is required after the stated condition" in prompt
    assert "Do not say the system prompts for a code, accepts a code, verifies a code" in prompt


def test_planner_permission_blocking_does_not_imply_positive_access():
    prompt = normalized(build_planner_system_prompt())

    assert "blocks users without a permission" in prompt
    assert "does not imply positive permitted-user access" in prompt


def test_generator_forbids_prompt_form_dialog_page_field_mechanism_unless_stated():
    prompt = normalized(build_generator_system_prompt())

    assert "Do not invent a prompt, form, dialog, page, screen, field widget" in prompt
    assert "unless it is explicitly stated" in prompt


def test_generator_forbids_authentication_completion_after_code_unless_stated():
    prompt = normalized(build_generator_system_prompt())

    assert "Do not invent completing authentication after OTP/code entry" in prompt
    assert "unless the requirement explicitly states successful authentication" in prompt
    assert "Do not say the system prompts for a code, accepts a code, verifies a code" in prompt


def test_generator_forbids_authenticated_logged_in_session_preconditions():
    prompt = normalized(build_generator_system_prompt())

    assert "Do not add authenticated, logged-in, or session preconditions unless stated" in prompt


def test_generator_forbids_positive_admin_access_case_for_non_admin_blocking_only():
    prompt = normalized(build_generator_system_prompt())

    assert "Do not invent positive administrator access case" in prompt
    assert "only states blocking users without administrator permission" in prompt


def test_reviewer_rejects_constraint_to_workflow_expansion():
    prompt = normalized(build_reviewer_system_prompt())

    assert "Reject if a test case expands a constraint into an unsupported workflow" in prompt


def test_reviewer_rejects_invented_cancellation_reason_prompt_field():
    prompt = normalized(build_reviewer_system_prompt())

    assert "Reject invented prompt, form, dialog, page, field" in prompt
    assert "for a required reason/value unless the source states that mechanism" in prompt
    assert "Reject required reason/value cases that say the larger action succeeds" in prompt


def test_reviewer_rejects_authentication_completion_after_code_unless_stated():
    prompt = normalized(build_reviewer_system_prompt())

    assert "Reject completing authentication after one-time-code/code entry" in prompt
    assert "unless the requirement explicitly states authentication completes" in prompt
    assert "Reject one-time-code/code entry cases that say the system prompts for" in prompt


def test_reviewer_rejects_positive_admin_access_case_unless_stated():
    prompt = normalized(build_reviewer_system_prompt())

    assert "Reject positive administrator access case when only non-admin blocking is stated" in prompt


def test_no_approved_status_exists():
    assert "APPROVED" not in ALLOWED_STATUSES


def test_no_repairer_py_exists():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_no_provider_routing_or_fallback_behavior_changed():
    router_text = Path("app/shared/llm/llm_router.py").read_text(encoding="utf-8")
    call_text = Path("app/shared/llm/call_llm.py").read_text(encoding="utf-8")

    assert "LLM_PROVIDER_ROUTING_MODE" in router_text
    assert "LLM_FALLBACK_POLICY" in router_text
    assert "LLM_ALLOWED_FALLBACKS" in router_text
    assert "CerebrasProvider" in router_text
    assert "GroqProvider" in router_text
    assert "LLM_CALL_TIMEOUT_SECONDS" in call_text


def test_no_production_keyword_or_domain_branching_added():
    forbidden_patterns = [
        'if "login" in',
        'if "dashboard" in',
        'if "button" in',
        'if "password" in',
        'if "download" in',
        'if "archive" in',
        'if "error" in',
        'if "ui" in',
        ".lower() in requirement",
        "requirement.lower(",
        "requirement_text.lower(",
    ]

    for path in PRODUCTION_FILES_TO_SCAN:
        text = path.read_text(encoding="utf-8").casefold()
        for pattern in forbidden_patterns:
            assert pattern.casefold() not in text, f"{pattern} found in {path}"


def test_mocked_cancellation_reason_prompt_form_field_is_rejected(monkeypatch):
    req = requirement("The system shall require a cancellation reason when an approved booking is cancelled.")
    test_case = case_with(
        req,
        steps=[
            TestStepModel(
                step_number=1,
                action="Open the cancellation form and leave the reason field blank.",
                expected_result="The system prompts for a cancellation reason.",
            )
        ],
        expected_result="The system prompts for a cancellation reason.",
        assumptions=["The cancellation form contains a reason field."],
    )

    decision = asyncio.run(
        reviewed_decision_for(monkeypatch, req, test_case, "invented prompt/form/field")
    )

    assert decision.decision == "REJECT_UNSUPPORTED_INVENTION"
    assert "invented prompt/form/field" in decision.unsupported_elements


def test_mocked_one_time_code_authentication_completion_is_rejected(monkeypatch):
    req = requirement(
        "The system shall require a user to enter a one-time code after submitting valid login credentials."
    )
    test_case = case_with(
        req,
        steps=[
            TestStepModel(
                step_number=1,
                action="Provide a valid one-time code.",
                expected_result="The system accepts the code and completes authentication.",
            )
        ],
        expected_result="The system completes authentication.",
    )

    decision = asyncio.run(
        reviewed_decision_for(monkeypatch, req, test_case, "authentication completion")
    )

    assert decision.decision == "REJECT_UNSUPPORTED_INVENTION"
    assert "authentication completion" in decision.unsupported_elements


def test_mocked_permission_blocking_authenticated_session_is_rejected(monkeypatch):
    req = requirement(
        "The system shall prevent users without administrator permission from opening the user management page."
    )
    test_case = case_with(
        req,
        preconditions=["Authenticated session is established for the user."],
        assumptions=["The user is authenticated."],
    )

    decision = asyncio.run(
        reviewed_decision_for(monkeypatch, req, test_case, "authenticated session precondition")
    )

    assert decision.decision == "REJECT_UNSUPPORTED_INVENTION"
    assert "authenticated session precondition" in decision.unsupported_elements


def test_mocked_permission_blocking_positive_admin_success_path_is_rejected(monkeypatch):
    req = requirement(
        "The system shall prevent users without administrator permission from opening the user management page."
    )
    test_case = case_with(
        req,
        title="Administrator opens user management page successfully",
        objective="Verify that an administrator can open the user management page.",
        steps=[
            TestStepModel(
                step_number=1,
                action="Exercise the configured action as an administrator.",
                expected_result="The user management page is accessible.",
            )
        ],
        expected_result="The user management page is accessible.",
    )

    decision = asyncio.run(
        reviewed_decision_for(monkeypatch, req, test_case, "positive administrator success path")
    )

    assert decision.decision == "REJECT_UNSUPPORTED_INVENTION"
    assert "positive administrator success path" in decision.unsupported_elements

