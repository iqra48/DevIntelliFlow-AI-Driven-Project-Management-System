import asyncio
from pathlib import Path

from app.services.test_case_generation.models import (
    ALLOWED_STATUSES,
    RequirementForTestCase,
    TestCase as TestCaseModel,
    TestStep as TestStepModel,
)
from app.services.test_case_generation.reviewer import review_batch
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
    build_generator_system_prompt,
    build_planner_system_prompt,
    build_reviewer_system_prompt,
)
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
    item = coverage_item("Verify stated behavior.")
    payload = {
        "test_case_id": f"TC_{requirement_obj.id}_001",
        "requirement_id": requirement_obj.id,
        "title": "Verify stated behavior",
        "objective": "Verify the stated behavior.",
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


def test_prompt_versions_are_phase15c_versions():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_planner_prompt_puts_unsupported_setup_in_missing_information():
    prompt = normalized(build_planner_system_prompt())

    assert "Planner assumptions must not invent product setup" in prompt
    assert "Put unsupported setup details in missing_information" in prompt
    assert "interface or entry point not specified" in prompt
    assert "permission model not specified" in prompt


def test_planner_prompt_has_semantic_balanced_coverage_target():
    prompt = normalized(build_planner_system_prompt())

    assert "BALANCED COVERAGE TARGET" in prompt
    assert "one Positive coverage item" in prompt
    assert "one Negative coverage item" in prompt
    assert "one Boundary coverage item" in prompt
    assert "semantic coverage target, not a fixed count rule" in prompt


def test_planner_prompt_forbids_invented_negative_or_boundary_coverage():
    prompt = normalized(build_planner_system_prompt())

    assert "Never invent unsupported Negative or Boundary coverage" in prompt
    assert "Do not force exactly three coverage items" in prompt
    assert "Negative coverage was not generated" in prompt
    assert "Boundary coverage was not generated" in prompt


def test_planner_prompt_forbids_unsupported_assumptions():
    prompt = build_planner_system_prompt()

    for phrase in [
        "form or interface exists",
        "user is logged in",
        "user is authenticated",
        "administrator has permission",
        "dashboard or post-login page exists",
        "Tab/Shift+Tab",
        "specific tool or measurement method exists",
        "system clock is synchronized",
        "scheduled process starts automatically",
    ]:
        assert phrase in prompt


def test_generator_prompt_forbids_unsupported_ui_auth_and_permissions():
    prompt = normalized(build_generator_system_prompt())

    for phrase in [
        "forms, interfaces",
        "pages, screens",
        "buttons, links",
        "dashboard redirects",
        "login sessions",
        "authenticated users",
        "permissions",
        "role permission setup",
    ]:
        assert phrase in prompt


def test_generator_prompt_forbids_tab_shift_tab_unless_stated():
    prompt = normalized(build_generator_system_prompt())

    assert "Tab/Shift+Tab behavior" in prompt
    assert "unless directly stated" in prompt


def test_generator_prompt_forbids_unsupported_nfr_setup():
    prompt = normalized(build_generator_system_prompt())

    for phrase in [
        "concrete performance/load tools",
        "load profiles",
        "load windows",
        "sample sizes",
        "concrete environments",
    ]:
        assert phrase in prompt


def test_generator_prompt_allows_generic_configured_wording():
    prompt = normalized(build_generator_system_prompt())

    assert "Configured prerequisites for exercising this capability are available." in prompt
    assert (
        "Configured measurement approach and representative operating conditions are available."
        in prompt
    )
    assert "Measure the stated NFR using the configured measurement approach." in prompt


def test_reviewer_prompt_rejects_unsupported_assumptions_and_preconditions():
    prompt = normalized(build_reviewer_system_prompt())

    assert "Reject unsupported invention even when it appears in assumptions or" in prompt
    assert "preconditions" in prompt


def test_reviewer_prompt_rejects_dashboard_redirect_unless_stated():
    prompt = normalized(build_reviewer_system_prompt())

    assert "dashboard redirects" in prompt
    assert "unless directly stated" in prompt


def test_reviewer_prompt_rejects_auth_login_permission_assumptions():
    prompt = build_reviewer_system_prompt()

    for phrase in ["authenticated users", "login state", "sessions", "permissions"]:
        assert phrase in prompt


def test_reviewer_prompt_rejects_tab_shift_tab_unless_stated():
    prompt = build_reviewer_system_prompt()

    assert "Tab/Shift+Tab" in prompt
    assert "unless directly stated" in prompt


def test_reviewer_prompt_rejects_unsupported_nfr_setup():
    prompt = build_reviewer_system_prompt()

    for phrase in [
        "specific tools",
        "load profiles",
        "load windows",
        "sample sizes",
        "concrete environments",
    ]:
        assert phrase in prompt


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


def test_mocked_login_case_with_dashboard_redirect_is_rejected(monkeypatch):
    req = requirement("The system shall allow a registered user to log in with a valid email address and password.")
    test_case = case_with(
        req,
        steps=[
            TestStepModel(
                step_number=1,
                action="Submit valid login credentials.",
                expected_result="The system redirects the user to the dashboard.",
            )
        ],
        expected_result="The user is redirected to the dashboard.",
        assumptions=["Dashboard is the expected post-login page."],
    )

    decision = asyncio.run(reviewed_decision_for(monkeypatch, req, test_case, "dashboard redirect"))

    assert decision.decision == "REJECT_UNSUPPORTED_INVENTION"
    assert "dashboard redirect" in decision.unsupported_elements


def test_mocked_notification_case_with_authenticated_precondition_is_rejected(monkeypatch):
    req = requirement("The system shall send an in-app notification when a submitted request is approved.")
    test_case = case_with(
        req,
        preconditions=["User is authenticated and can view in-app notifications."],
        assumptions=["User is authenticated."],
    )

    decision = asyncio.run(reviewed_decision_for(monkeypatch, req, test_case, "authenticated user precondition"))

    assert decision.decision == "REJECT_UNSUPPORTED_INVENTION"
    assert "authenticated user precondition" in decision.unsupported_elements


def test_mocked_keyboard_case_with_tab_shift_tab_is_rejected(monkeypatch):
    req = requirement("The system shall provide keyboard navigation for all primary form fields.", kind="NFR")
    test_case = case_with(
        req,
        objective="Verify users can navigate using Tab/Shift+Tab.",
        steps=[
            TestStepModel(
                step_number=1,
                action="Use Tab/Shift+Tab to move between primary form fields.",
                expected_result="Focus moves between fields.",
            )
        ],
        expected_result="Users can navigate using Tab/Shift+Tab.",
    )

    decision = asyncio.run(reviewed_decision_for(monkeypatch, req, test_case, "Tab/Shift+Tab"))

    assert decision.decision == "REJECT_UNSUPPORTED_INVENTION"
    assert "Tab/Shift+Tab" in decision.unsupported_elements


def test_mocked_nfr_case_with_invented_load_tool_window_is_rejected(monkeypatch):
    req = requirement("The system shall load the project dashboard within three seconds for 95 percent of requests.", kind="NFR")
    test_case = case_with(
        req,
        preconditions=["JMeter is configured for a 30-minute load test with 100 users."],
        steps=[
            TestStepModel(
                step_number=1,
                action="Run the JMeter test for 30 minutes with 100 users.",
                expected_result="95 percent of requests complete within three seconds.",
            )
        ],
        assumptions=["JMeter and the 30-minute load window are available."],
    )

    decision = asyncio.run(reviewed_decision_for(monkeypatch, req, test_case, "invented load tool/window"))

    assert decision.decision == "REJECT_UNSUPPORTED_INVENTION"
    assert "invented load tool/window" in decision.unsupported_elements


