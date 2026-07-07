from pathlib import Path

from app.services.test_case_generation.models import ALLOWED_STATUSES, RequirementForTestCase
from app.services.test_case_generation.planner import parse_planner_response
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
    build_planner_system_prompt,
)


def test_planner_prompt_distinguishes_blocking_and_non_blocking_missing_information():
    prompt = build_planner_system_prompt()

    assert "BLOCKING VS NON-BLOCKING MISSING INFORMATION" in prompt
    assert "Blocking missing information means" in prompt
    assert "Non-blocking missing information means" in prompt


def test_planner_prompt_observable_frs_not_blocked_for_missing_implementation_details():
    prompt = " ".join(build_planner_system_prompt().split())

    assert "For observable FRs, do not block only because implementation details are absent" in prompt
    assert "exact success" in prompt
    assert "exact credential format" in prompt
    assert "exact report format" in prompt


def test_planner_prompt_measurable_nfrs_not_blocked_for_missing_setup_details():
    prompt = " ".join(build_planner_system_prompt().split())

    assert "For measurable NFRs, do not block only because measurement setup details are absent" in prompt
    assert "measurement method" in prompt
    assert "measurable criterion" in prompt


def test_planner_prompt_vague_nfrs_without_measurable_criteria_blocked():
    prompt = build_planner_system_prompt()

    assert "For vague NFRs without measurable criteria" in prompt
    assert "blocking_missing_information" in prompt
    assert "Do not invent fake metrics" in prompt


def test_no_python_production_keyword_branches_added():
    production_files = [
        path
        for path in Path("app/services/test_case_generation").glob("*.py")
        if path.name != "prompts.py"
    ] + [
        Path("app/shared/llm/llm_router.py"),
        Path("app/shared/llm/call_llm.py"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in production_files)

    forbidden = [
        'if "login" in',
        "if 'login' in",
        'if "report" in',
        "if 'report' in",
        'if "upload" in',
        "if 'upload' in",
        'if "dashboard" in',
        "if 'dashboard' in",
        'if "usability" in',
        "if 'usability' in",
        'if "performance" in',
        "if 'performance' in",
        'if "password" in',
        "if 'password' in",
        "requirement.lower(",
        "requirement.casefold(",
    ]
    for pattern in forbidden:
        assert pattern not in combined


def test_planner_prompt_version_bumped_to_planner_v13():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_no_approved_status_exists():
    assert "APPROVED" not in ALLOWED_STATUSES


def test_no_repairer_py_exists():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_provider_strategy_docs_still_contain_hybrid_signature():
    assert (
        "planner=cerebras|generator=groq|reviewer=cerebras"
        in Path("docs/provider_strategy.md").read_text(encoding="utf-8")
    )


def test_mocked_safe_planner_output_for_login_validates():
    requirement = RequirementForTestCase(
        id="REQ_1",
        requirement="The system shall allow users to log in.",
        classification_type="FR",
    )
    parsed = parse_planner_response(
        {
            "plans": {
                "1": {
                    "requirement_id": "REQ_1",
                    "requirement_text": "The system shall allow users to log in.",
                    "requirement_type": "FR",
                    "testable": True,
                    "safe_to_generate": True,
                    "risk_ref": "RISK_MEDIUM",
                    "ambiguity_ref": "AMBIGUITY_MEDIUM",
                    "blocking_missing_information": [],
                    "missing_information": [
                        "Exact authentication method and credential format are not specified."
                    ],
                    "coverage_items": [
                        {
                            "coverage_item": "Verify users can log in using configured valid credentials",
                            "source_basis": ["allow users to log in"],
                            "test_type_ref": "TT_POSITIVE",
                            "technique_used": "Functional verification",
                            "priority_ref": "PRIORITY_HIGH",
                            "rationale": "Covers the observable login capability stated by the requirement.",
                        }
                    ],
                    "recommended_test_case_count": 1,
                    "assumptions": [
                        "Configured prerequisites for exercising this capability are available."
                    ],
                }
            }
        },
        [requirement],
    )

    plan = parsed["REQ_1"]
    assert plan.safe_to_generate is True
    assert plan.recommended_test_case_count == 1
    assert plan.missing_information


def test_mocked_safe_planner_output_for_measurable_performance_nfr_validates():
    requirement = RequirementForTestCase(
        id="REQ_1",
        requirement="The system shall respond to dashboard requests within 2 seconds.",
        classification_type="NFR",
    )
    parsed = parse_planner_response(
        {
            "plans": {
                "1": {
                    "requirement_id": "REQ_1",
                    "requirement_text": "The system shall respond to dashboard requests within 2 seconds.",
                    "requirement_type": "NFR",
                    "testable": True,
                    "safe_to_generate": True,
                    "risk_ref": "RISK_MEDIUM",
                    "ambiguity_ref": "AMBIGUITY_MEDIUM",
                    "blocking_missing_information": [],
                    "missing_information": [
                        "Measurement method, test environment, and load profile are not specified."
                    ],
                    "coverage_items": [
                        {
                            "coverage_item": "Verify measured dashboard request response time is within 2 seconds",
                            "source_basis": ["respond to dashboard requests within 2 seconds"],
                            "test_type_ref": "TT_PERFORMANCE",
                            "technique_used": "Performance measurement",
                            "priority_ref": "PRIORITY_HIGH",
                            "rationale": "Covers the stated measurable response-time threshold.",
                        }
                    ],
                    "recommended_test_case_count": 1,
                    "assumptions": [
                        "Configured measurement approach and representative operating conditions are available."
                    ],
                }
            }
        },
        [requirement],
    )

    plan = parsed["REQ_1"]
    assert plan.safe_to_generate is True
    assert plan.coverage_items[0].test_type == "Performance"
    assert plan.missing_information


def test_mocked_blocked_planner_output_for_vague_usability_nfr_validates():
    requirement = RequirementForTestCase(
        id="REQ_1",
        requirement="The application shall be easy to use.",
        classification_type="NFR",
    )
    parsed = parse_planner_response(
        {
            "plans": {
                "1": {
                    "requirement_id": "REQ_1",
                    "requirement_text": "The application shall be easy to use.",
                    "requirement_type": "NFR",
                    "testable": False,
                    "safe_to_generate": False,
                    "risk_ref": "RISK_MEDIUM",
                    "ambiguity_ref": "AMBIGUITY_HIGH",
                    "blocking_missing_information": [
                        "Measurable usability criteria are not specified."
                    ],
                    "missing_information": [],
                    "coverage_items": [],
                    "recommended_test_case_count": 0,
                    "assumptions": [],
                }
            }
        },
        [requirement],
    )

    plan = parsed["REQ_1"]
    assert plan.safe_to_generate is False
    assert plan.recommended_test_case_count == 0
    assert plan.blocking_missing_information


