import asyncio
import re
from pathlib import Path

from app.services.test_case_generation.models import (
    ALLOWED_STATUSES,
    RequirementForTestCase,
    TestCase as TestCaseModel,
    TestStep as TestStepModel,
)
from app.services.test_case_generation.planner import parse_planner_response
from app.services.test_case_generation.prompts import (
    PLANNER_TECHNIQUE_OPTIONS,
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
    build_generator_system_prompt,
    build_planner_system_prompt,
    build_planner_user_prompt,
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


def requirement(text: str = "The system shall process item REQ_1.", kind: str = "FR"):
    return RequirementForTestCase(
        id="REQ_1",
        requirement=text,
        classification_type=kind,
    )


def planner_coverage(**overrides):
    data = {
        "coverage_item": "Verify stated behavior.",
        "source_basis": ["The system shall process item REQ_1."],
        "test_type_ref": "TT_POSITIVE",
        "test_type": "Positive",
        "technique_ref": "TECH_FUNCTIONAL",
        "technique_used": "Functional verification",
        "priority_ref": "PRIORITY_HIGH",
        "priority": "High",
        "rationale": "Covers planned behavior.",
    }
    data.update(overrides)
    return data


def planner_payload(req, coverage=None):
    return {
        "plans": {
            "1": {
                "requirement_id": req.id,
                "requirement_text": req.requirement,
                "requirement_type": req.classification_type,
                "testable": True,
                "safe_to_generate": True,
                "risk_ref": "RISK_MEDIUM",
                "risk_level": "Medium",
                "ambiguity_ref": "AMBIGUITY_LOW",
                "ambiguity_level": "Low",
                "blocking_missing_information": [],
                "missing_information": [],
                "coverage_items": [coverage or planner_coverage()],
                "recommended_test_case_count": 1,
                "assumptions": [],
            }
        }
    }


def parsed_plan(req, coverage):
    return parse_planner_response(planner_payload(req, coverage), [req])[req.id]


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


def test_prompt_versions_are_phase15e_versions():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_prompts_define_planner_technique_options():
    assert PLANNER_TECHNIQUE_OPTIONS
    assert all("technique_ref" in item for item in PLANNER_TECHNIQUE_OPTIONS)
    assert all("technique_used" in item for item in PLANNER_TECHNIQUE_OPTIONS)


def test_planner_technique_options_are_neutral_labels():
    values = {item["technique_used"] for item in PLANNER_TECHNIQUE_OPTIONS}

    assert "Functional verification" in values
    assert "Performance measurement" in values
    assert "Usability and accessibility verification" in values


def test_planner_technique_options_do_not_contain_mechanism_terms():
    forbidden = [
        "UI",
        "form",
        "web interface",
        "API",
        "Tab",
        "Shift+Tab",
        "Manual",
        "browser",
        "page",
        "screen",
        "button",
        "clock synchronization",
    ]
    combined = "\n".join(item["technique_used"] for item in PLANNER_TECHNIQUE_OPTIONS)

    for term in forbidden:
        assert re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", combined) is None


def test_planner_prompt_requires_technique_ref():
    assert "include technique_ref" in build_planner_system_prompt()


def test_planner_prompt_requires_exact_technique_copy_from_ref():
    prompt = normalized(build_planner_system_prompt())

    assert "copy technique_used exactly from that technique_ref" in prompt


def test_planner_prompt_blocks_mechanism_examples_without_source_basis():
    prompt = normalized(build_planner_system_prompt())

    assert "coverage_item must not include examples in parentheses" in prompt
    assert "(e.g., Tab key)" in prompt
    assert "unless the exact example appears in source_basis" in prompt


def test_planner_user_prompt_includes_technique_enum_options():
    prompt = build_planner_user_prompt([requirement()])

    assert '"technique":' in prompt
    assert "TECH_FUNCTIONAL" in prompt


def test_planner_resolves_technique_ref_to_canonical_technique_used():
    req = requirement()
    plan = parsed_plan(
        req,
        planner_coverage(technique_ref="TECH_FUNCTIONAL", technique_used="Wrong"),
    )

    assert plan.coverage_items[0].technique_used == "Functional verification"


def test_planner_rejects_arbitrary_free_text_technique_used():
    req = requirement()
    coverage = planner_coverage(technique_used="Functional UI form submission")
    del coverage["technique_ref"]
    plan = parsed_plan(req, coverage)

    assert plan.safe_to_generate is False
    assert plan.coverage_items == []


def test_generator_prompt_requires_traceability_technique_exact_match():
    prompt = normalized(build_generator_system_prompt())

    assert "traceability.technique_used must equal the selected planner technique_used exactly" in prompt


def test_generator_prompt_requires_traceability_coverage_exact_match():
    prompt = normalized(build_generator_system_prompt())

    assert "traceability.coverage_item must equal the selected planner coverage_item exactly" in prompt


def test_reviewer_prompt_checks_traceability_fields():
    prompt = normalized(build_reviewer_system_prompt())

    assert "traceability.coverage_item" in prompt
    assert "traceability.technique_used" in prompt


def test_reviewer_prompt_rejects_unsupported_mechanisms_in_technique():
    prompt = normalized(build_reviewer_system_prompt())

    assert "Reject technique labels or traceability fields" in prompt
    assert "web interface" in prompt
    assert "API" in prompt


def test_reviewer_prompt_rejects_tab_shift_tab_unless_stated():
    prompt = normalized(build_reviewer_system_prompt())

    assert "Reject coverage_item examples such as" in prompt
    assert "e.g., Tab key" in prompt
    assert "unless source_basis explicitly says Tab" in prompt


def test_reviewer_prompt_rejects_synchronized_clock_precondition_unless_stated():
    prompt = normalized(build_reviewer_system_prompt())

    assert "Reject \"System clock is synchronized\"" in prompt
    assert "unless source explicitly says synchronized clock" in prompt


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


def test_parser_rejects_functional_ui_form_submission_technique():
    req = requirement()
    coverage = planner_coverage(technique_used="Functional UI form submission")
    del coverage["technique_ref"]
    plan = parsed_plan(req, coverage)

    assert plan.safe_to_generate is False


def test_parser_rejects_manual_download_web_interface_technique():
    req = requirement()
    coverage = planner_coverage(technique_used="Manual download via web interface")
    del coverage["technique_ref"]
    plan = parsed_plan(req, coverage)

    assert plan.safe_to_generate is False


def test_mocked_reviewer_rejects_traceability_web_interface(monkeypatch):
    req = requirement("The system shall allow a user to download a report as a PDF file.")
    test_case = case_with(
        req,
        traceability={
            "requirement_id": req.id,
            "coverage_item": "Verify report download as PDF.",
            "technique_used": "Manual download via web interface",
        },
    )

    decision = asyncio.run(reviewed_decision_for(monkeypatch, req, test_case, "web interface"))

    assert decision.decision == "REJECT_UNSUPPORTED_INVENTION"
    assert "web interface" in decision.unsupported_elements


def test_mocked_reviewer_rejects_tab_key_coverage_example(monkeypatch):
    req = requirement("The system shall provide keyboard navigation for all primary form fields.", "NFR")
    test_case = case_with(
        req,
        traceability={
            "requirement_id": req.id,
            "coverage_item": "Verify keyboard navigation (e.g., Tab key) through fields.",
            "technique_used": "Usability and accessibility verification",
        },
    )

    decision = asyncio.run(reviewed_decision_for(monkeypatch, req, test_case, "Tab key"))

    assert decision.decision == "REJECT_UNSUPPORTED_INVENTION"
    assert "Tab key" in decision.unsupported_elements


def test_mocked_reviewer_rejects_synchronized_clock_precondition(monkeypatch):
    req = requirement("The system shall complete nightly report generation before 6:00 AM local time.", "NFR")
    test_case = case_with(
        req,
        preconditions=["System clock is synchronized to local time."],
        assumptions=["System clock is synchronized to local time."],
    )

    decision = asyncio.run(
        reviewed_decision_for(monkeypatch, req, test_case, "synchronized clock")
    )

    assert decision.decision == "REJECT_UNSUPPORTED_INVENTION"
    assert "synchronized clock" in decision.unsupported_elements
