from pathlib import Path

import pytest

from app.services.test_case_generation import cache as cache_module
from app.services.test_case_generation.cache import build_cache_key
from app.services.test_case_generation.generator import parse_generator_response
from app.services.test_case_generation.models import (
    CoverageItem,
    PlannerOutput,
    RequirementForTestCase,
    TestCase as CaseModel,
    TestCaseBundle as BundleModel,
    TestStep as StepModel,
)
from app.services.test_case_generation.planner import parse_planner_response
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    build_generator_system_prompt,
    build_generator_user_prompt,
    build_planner_system_prompt,
)
from app.services.test_case_generation.validation import (
    TestCaseValidationError,
    validate_bundle_against_plan,
    validate_planner_output_against_requirement,
    validate_test_case_against_requirement,
)


def requirement(requirement_id="REQ_1", text=None, requirement_type="FR"):
    return RequirementForTestCase(
        id=requirement_id,
        requirement=text or f"The system shall process item {requirement_id}.",
        classification_type=requirement_type,
    )


def coverage_item(**overrides):
    data = {
        "coverage_item": "Verify stated behavior.",
        "source_basis": ["The system shall process item REQ_1."],
        "test_type_ref": "TT_POSITIVE",
        "test_type": "Positive",
        "technique_used": "Functional verification",
        "priority_ref": "PRIORITY_HIGH",
        "priority": "High",
        "rationale": "Covers planned behavior.",
    }
    data.update(overrides)
    return data


def coverage_model(**overrides):
    data = {
        "coverage_item": "Verify stated behavior.",
        "source_basis": ["The system shall process item REQ_1."],
        "test_type": "Positive",
        "technique_used": "Functional verification",
        "priority": "High",
        "rationale": "Covers planned behavior.",
    }
    data.update(overrides)
    return CoverageItem(**data)


def plan_dict(req, **overrides):
    data = {
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
        "coverage_items": [coverage_item()],
        "recommended_test_case_count": 1,
        "assumptions": [],
    }
    data.update(overrides)
    return data


def plan_model(req=None, item=None):
    req = req or requirement()
    item = item or coverage_model()
    return PlannerOutput(
        requirement_id=req.id,
        requirement_text=req.requirement,
        requirement_type=req.classification_type,
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


def blocked_plan_dict(req):
    return plan_dict(
        req,
        testable=False,
        safe_to_generate=False,
        ambiguity_ref="AMBIGUITY_HIGH",
        ambiguity_level="High",
        blocking_missing_information=["Missing observable behavior"],
        coverage_items=[],
        recommended_test_case_count=0,
    )


def response_for_plan(raw_plan):
    return {"plans": {"1": raw_plan}}


def case_payload(req, coverage_ref="COV_1", source_basis=None):
    payload = {
        "test_case_id": f"TC_{req.id}_001",
        "requirement_id": req.id,
        "title": "Verify planned behavior",
        "objective": "Confirm the requirement is satisfied.",
        "test_type": "Changed",
        "technique_used": "Changed",
        "priority": "Low",
        "preconditions": ["System is available."],
        "test_data": {},
        "steps": [
            {
                "step_number": 1,
                "action": "Perform verification.",
                "expected_result": "Expected outcome is observed.",
            }
        ],
        "expected_result": "The requirement is satisfied.",
        "assumption_required": False,
        "assumptions": [],
        "traceability": {
            "requirement_id": req.id,
            "coverage_ref": coverage_ref,
            "coverage_item": "Changed",
            "technique_used": "Changed",
        },
    }
    if source_basis is not None:
        payload["source_basis"] = source_basis
    return payload


def bundle_payload(req, cases):
    return {
        "requirement_id": req.id,
        "requirement_text": req.requirement,
        "requirement_type": req.classification_type,
        "test_cases": cases,
        "warnings": [],
    }


def response_for_bundle(req, cases):
    return {"bundles": {"1": bundle_payload(req, cases)}}


def test_coverage_item_supports_source_basis():
    item = coverage_model(source_basis=["stated phrase"])

    assert item.source_basis == ["stated phrase"]


def test_coverage_item_from_dict_defaults_missing_source_basis_to_empty():
    item = CoverageItem.from_dict(
        {
            "coverage_item": "Verify behavior.",
            "test_type": "Positive",
            "technique_used": "Manual",
            "priority": "High",
            "rationale": "Covers behavior.",
        }
    )

    assert item.source_basis == []


def test_test_case_supports_source_basis():
    case = make_test_case_model(source_basis=["stated phrase"])

    assert case.source_basis == ["stated phrase"]


def test_test_case_from_dict_defaults_missing_source_basis_to_empty():
    case = CaseModel.from_dict(make_test_case_model().to_dict() | {"source_basis": []})
    payload = case.to_dict()
    del payload["source_basis"]

    assert CaseModel.from_dict(payload).source_basis == []


def test_planner_prompt_version_is_planner_v13():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"


def test_generator_prompt_version_is_generator_v8():
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"


def test_planner_system_prompt_mentions_source_grounded_coverage():
    assert "SOURCE-GROUNDED COVERAGE" in build_planner_system_prompt()


def test_planner_system_prompt_says_source_basis_is_required():
    prompt = build_planner_system_prompt()

    assert "include source_basis as list[str]" in prompt


def test_planner_system_prompt_blocks_unsupported_negative_error_failure_coverage():
    prompt = build_planner_system_prompt()

    assert "Do not create negative, invalid-input, missing-precondition" in prompt
    assert "or failure coverage unless" in prompt


def test_planner_system_prompt_blocks_vague_tautological_tests():
    prompt = build_planner_system_prompt()

    assert "vague requirements" in prompt
    assert "non-tautological expected results" in prompt


def test_planner_system_prompt_blocks_nfr_failure_expectation():
    prompt = build_planner_system_prompt()

    assert "expected result is that the system fails" in prompt
    assert "to meet the NFR" in prompt


def test_generator_system_prompt_mentions_source_grounded_test_cases():
    assert "SOURCE-GROUNDED TEST CASES" in build_generator_system_prompt()


def test_generator_system_prompt_says_source_basis_copied_from_coverage_ref():
    prompt = build_generator_system_prompt()

    assert "source_basis copied from the selected" in prompt
    assert "coverage_ref" in prompt


def test_generator_user_prompt_includes_source_basis_inside_coverage_refs():
    req = requirement()
    plan = plan_model(req)

    prompt = build_generator_user_prompt([req], {req.id: plan})

    assert '"source_basis": ["The system shall process item REQ_1."]' in prompt


def test_parse_planner_response_accepts_coverage_item_with_source_basis():
    req = requirement()
    result = parse_planner_response(response_for_plan(plan_dict(req)), [req])

    assert result[req.id].coverage_items[0].source_basis == [
        "The system shall process item REQ_1."
    ]


def test_parse_planner_response_rejects_coverage_item_missing_source_basis():
    req = requirement()
    raw = coverage_item()
    del raw["source_basis"]

    result = parse_planner_response(
        response_for_plan(plan_dict(req, coverage_items=[raw])),
        [req],
    )

    assert result[req.id].safe_to_generate is False
    assert "source_basis" in result[req.id].blocking_missing_information[0]


def test_parse_planner_response_rejects_empty_source_basis():
    req = requirement()
    result = parse_planner_response(
        response_for_plan(plan_dict(req, coverage_items=[coverage_item(source_basis=[])])),
        [req],
    )

    assert result[req.id].safe_to_generate is False


def test_parse_planner_response_rejects_non_list_source_basis():
    req = requirement()
    result = parse_planner_response(
        response_for_plan(
            plan_dict(req, coverage_items=[coverage_item(source_basis="phrase")])
        ),
        [req],
    )

    assert result[req.id].safe_to_generate is False


def test_blocked_planner_output_with_empty_coverage_items_still_parses():
    req = requirement()
    result = parse_planner_response(response_for_plan(blocked_plan_dict(req)), [req])

    assert result[req.id].safe_to_generate is False
    assert result[req.id].coverage_items == []


def test_parse_generator_response_canonicalizes_source_basis_from_planner():
    req = requirement()
    plan = plan_model(req, coverage_model(source_basis=["planner phrase"]))

    bundle = parse_generator_response(
        response_for_bundle(req, [case_payload(req, source_basis=["raw phrase"])]),
        [req],
        {req.id: plan},
    )[req.id]

    assert bundle.test_cases[0].source_basis == ["planner phrase"]


def test_generator_raw_source_basis_is_ignored_when_coverage_ref_is_valid():
    req = requirement()
    plan = plan_model(req, coverage_model(source_basis=["planner-owned phrase"]))

    bundle = parse_generator_response(
        response_for_bundle(req, [case_payload(req, source_basis=["generator phrase"])]),
        [req],
        {req.id: plan},
    )[req.id]

    assert bundle.test_cases[0].source_basis == ["planner-owned phrase"]


def test_source_basis_is_preserved_with_fallback_exact_coverage_item():
    req = requirement()
    item = coverage_model(source_basis=["fallback phrase"])
    plan = plan_model(req, item)
    raw_case = case_payload(req)
    raw_case["traceability"] = {
        "requirement_id": req.id,
        "coverage_item": item.coverage_item,
        "technique_used": "Changed",
    }

    bundle = parse_generator_response(
        response_for_bundle(req, [raw_case]),
        [req],
        {req.id: plan},
    )[req.id]

    assert bundle.test_cases[0].source_basis == ["fallback phrase"]


def test_missing_raw_source_basis_still_succeeds_from_planner_source_basis():
    req = requirement()
    plan = plan_model(req, coverage_model(source_basis=["planner phrase"]))

    bundle = parse_generator_response(
        response_for_bundle(req, [case_payload(req)]),
        [req],
        {req.id: plan},
    )[req.id]

    assert bundle.status == "SUCCESS"
    assert bundle.test_cases[0].source_basis == ["planner phrase"]


def test_parsed_generated_test_case_source_basis_equals_planned_coverage_source_basis():
    req = requirement()
    item = coverage_model(source_basis=["exact planner phrase"])
    plan = plan_model(req, item)

    bundle = parse_generator_response(
        response_for_bundle(req, [case_payload(req)]),
        [req],
        {req.id: plan},
    )[req.id]

    assert bundle.test_cases[0].source_basis == item.source_basis


def test_validate_planner_output_against_requirement_rejects_coverage_without_source_basis():
    req = requirement()
    plan = plan_model(req, coverage_model(source_basis=[]))

    with pytest.raises(TestCaseValidationError):
        validate_planner_output_against_requirement(plan, req)


def test_validate_test_case_against_requirement_rejects_case_without_source_basis():
    req = requirement()
    case = make_test_case_model(req, source_basis=[])

    with pytest.raises(TestCaseValidationError):
        validate_test_case_against_requirement(case, req)


def test_validate_bundle_against_plan_rejects_source_basis_divergence():
    req = requirement()
    item = coverage_model(source_basis=["planner phrase"])
    plan = plan_model(req, item)
    case = make_test_case_model(req, item, source_basis=["different phrase"])
    bundle = BundleModel(
        requirement_id=req.id,
        requirement_text=req.requirement,
        requirement_type=req.classification_type,
        status="SUCCESS",
        test_cases=[case],
        missing_information=[],
        assumptions=[],
        warnings=[],
    )

    validated = validate_bundle_against_plan(bundle, plan)

    assert validated.status == "FAILED_SCHEMA_VALIDATION"


def test_valid_source_basis_passes_structural_and_planner_consistency_validation():
    req = requirement()
    item = coverage_model(source_basis=["planner phrase"])
    plan = plan_model(req, item)
    case = make_test_case_model(req, item, source_basis=list(item.source_basis))
    bundle = BundleModel(
        requirement_id=req.id,
        requirement_text=req.requirement,
        requirement_type=req.classification_type,
        status="SUCCESS",
        test_cases=[case],
        missing_information=[],
        assumptions=[],
        warnings=[],
    )

    assert validate_test_case_against_requirement(case, req) is case
    assert validate_bundle_against_plan(bundle, plan).status == "SUCCESS"


def test_cache_key_changes_because_prompt_versions_changed(monkeypatch):
    req = requirement()
    before = build_cache_key([req], "ctx", "mvp_fast")

    monkeypatch.setattr(cache_module, "TEST_CASE_PROMPT_VERSION", "planner_v3")
    monkeypatch.setattr(cache_module, "TEST_CASE_GENERATOR_PROMPT_VERSION", "generator_v2")

    assert before != build_cache_key([req], "ctx", "mvp_fast")


def test_prompt_tells_planner_not_to_invent_post_conditions():
    assert "Do not invent post-conditions" in build_planner_system_prompt()


def test_prompt_tells_generator_not_to_create_extra_invalid_precondition_error_cases():
    prompt = build_generator_system_prompt()

    assert "Do not create extra negative/error/invalid/precondition cases" in prompt


def test_prompt_tells_vague_requirements_to_block_instead_of_tautological_tests():
    prompt = build_planner_system_prompt()

    assert "set safe_to_generate=false" in prompt
    assert "non-tautological" in prompt


def test_prompt_tells_generator_not_to_invent_default_locale_auth_visibility_assumptions():
    prompt = build_generator_system_prompt()

    assert "Do not add behavior that is not supported by source_basis" in prompt
    assert "Do not invent post-state outcomes" in prompt


def test_no_requirement_lower_in_phase12h_files():
    combined = phase12h_implementation_text()

    assert "requirement" + "." + "low" + "er(" not in combined


def test_no_keyword_branch_implementation_in_phase12h_files():
    combined = phase12h_implementation_text()
    forbidden = [
        'if "' + "login" + '" in',
        'if "' + "password" + '" in',
        'if "' + "payment" + '" in',
        'if "' + "security" + '" in',
        'if "' + "download" + '" in',
        'if "' + "archive" + '" in',
        "keyword-to" + "-test-type maps",
        "keyword-to" + "-technique maps",
        "hardcoded business" + "/domain routing",
    ]

    for fragment in forbidden:
        assert fragment not in combined


def test_no_unapproved_matching_helpers_in_phase12h_files():
    combined = phase12h_implementation_text()
    forbidden = [
        "fu" + "zzy",
        "sim" + "ilarity",
        "con" + "tains(",
        "start" + "swith(",
        "." + "low" + "er(",
    ]

    for fragment in forbidden:
        assert fragment not in combined


def test_validation_does_not_inspect_requirement_text_for_source_basis():
    req = requirement(text="The system shall process records.")
    item = coverage_model(source_basis=["Project context phrase"])
    plan = plan_model(req, item)

    assert validate_planner_output_against_requirement(plan, req) is plan


def make_test_case_model(req=None, item=None, source_basis=None):
    req = req or requirement()
    item = item or coverage_model()
    return CaseModel(
        test_case_id=f"TC_{req.id}_001",
        requirement_id=req.id,
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
        traceability={
            "requirement_id": req.id,
            "coverage_item": item.coverage_item,
            "technique_used": item.technique_used,
        },
        source_basis=list(item.source_basis) if source_basis is None else source_basis,
    )


def phase12h_implementation_text():
    return "\n".join(
        Path(path).read_text()
        for path in [
            "app/services/test_case_generation/models.py",
            "app/services/test_case_generation/planner.py",
            "app/services/test_case_generation/generator.py",
            "app/services/test_case_generation/validation.py",
        ]
    )


