from pathlib import Path

from app.services.test_case_generation import cache as cache_module
from app.services.test_case_generation.cache import build_cache_key
from app.services.test_case_generation.generator import parse_generator_response
from app.services.test_case_generation.models import (
    CoverageItem,
    PlannerOutput,
    RequirementForTestCase,
)
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    build_generator_system_prompt,
    build_generator_user_prompt,
)
from app.services.test_case_generation.validation import (
    validate_bundles_against_source_and_plan,
)


def requirement(requirement_id="REQ_1", requirement_type="FR"):
    return RequirementForTestCase(
        id=requirement_id,
        requirement=f"The system shall process item {requirement_id}.",
        classification_type=requirement_type,
    )


def coverage_item(
    name="Verify stated behavior.",
    test_type="Positive",
    technique="Functional verification",
    priority="High",
):
    return CoverageItem(
        coverage_item=name,
        source_basis=[f"The system shall process item REQ_1."],
        test_type=test_type,
        technique_used=technique,
        priority=priority,
        rationale="Covers planned behavior.",
    )


def plan_for(req, items=None):
    items = items or [coverage_item()]
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
        coverage_items=items,
        recommended_test_case_count=len(items),
        assumptions=[],
    )


def case_payload(req, coverage_ref="COV_1", coverage_text="Changed text"):
    traceability = {
        "requirement_id": req.id,
        "coverage_ref": coverage_ref,
        "coverage_item": coverage_text,
        "technique_used": "Changed technique",
    }
    return {
        "test_case_id": f"TC_{req.id}_001",
        "requirement_id": req.id,
        "title": "Verify planned behavior",
        "objective": "Confirm the requirement is satisfied.",
        "test_type": "Negative",
        "technique_used": "Changed technique",
        "priority": "Low",
        "preconditions": ["System is available."],
        "test_data": {},
        "steps": [
            {
                "step_number": 1,
                "action": "Perform the planned verification.",
                "expected_result": "The expected outcome is observed.",
            }
        ],
        "expected_result": "The requirement is satisfied.",
        "assumption_required": False,
        "assumptions": [],
        "traceability": traceability,
    }


def bundle_payload(req, cases):
    return {
        "requirement_id": req.id,
        "requirement_text": req.requirement,
        "requirement_type": req.classification_type,
        "test_cases": cases,
        "warnings": [],
    }


def response_for(*bundles):
    return {"bundles": {str(index): bundle for index, bundle in enumerate(bundles, 1)}}


def parsed_bundle(req, plan, raw_case):
    result = parse_generator_response(
        response_for(bundle_payload(req, [raw_case])),
        [req],
        {req.id: plan},
    )
    return result[req.id]


def test_generator_prompt_version_is_generator_v8():
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"


def test_build_generator_user_prompt_includes_coverage_ref_values():
    req = requirement()
    plans = {req.id: plan_for(req)}

    prompt = build_generator_user_prompt([req], plans)

    assert '"coverage_ref": "COV_1"' in prompt


def test_build_generator_user_prompt_includes_exact_coverage_item_text():
    req = requirement()
    item = coverage_item(name="Exact coverage item text.")
    plans = {req.id: plan_for(req, [item])}

    prompt = build_generator_user_prompt([req], plans)

    assert "Exact coverage item text." in prompt


def test_build_generator_user_prompt_includes_recommended_test_case_count():
    req = requirement()
    plans = {req.id: plan_for(req)}

    prompt = build_generator_user_prompt([req], plans)

    assert "recommended_test_case_count=1" in prompt


def test_build_generator_system_prompt_instructs_coverage_ref_usage():
    prompt = build_generator_system_prompt()

    assert "coverage_ref" in prompt
    assert "Select one supplied coverage_ref for every test case" in prompt


def test_parse_generator_response_accepts_valid_coverage_ref_cov_1():
    req = requirement()
    plan = plan_for(req)

    bundle = parsed_bundle(req, plan, case_payload(req, coverage_ref="COV_1"))

    assert bundle.status == "SUCCESS"
    assert len(bundle.test_cases) == 1


def test_parse_generator_response_canonicalizes_changed_coverage_item_with_valid_ref():
    req = requirement()
    item = coverage_item(name="Planner exact coverage.")
    plan = plan_for(req, [item])

    bundle = parsed_bundle(req, plan, case_payload(req, coverage_text="Different"))

    assert bundle.test_cases[0].traceability["coverage_item"] == "Planner exact coverage."


def test_canonicalized_traceability_coverage_item_equals_planner_exactly():
    req = requirement()
    item = coverage_item(name="Planner coverage item.")
    plan = plan_for(req, [item])

    bundle = parsed_bundle(req, plan, case_payload(req))

    assert bundle.test_cases[0].traceability["coverage_item"] == item.coverage_item


def test_canonicalized_technique_used_equals_planner_exactly():
    req = requirement()
    item = coverage_item(technique="Planner technique")
    plan = plan_for(req, [item])

    bundle = parsed_bundle(req, plan, case_payload(req))

    assert bundle.test_cases[0].technique_used == item.technique_used
    assert bundle.test_cases[0].traceability["technique_used"] == item.technique_used


def test_canonicalized_test_type_equals_planner_exactly():
    req = requirement()
    item = coverage_item(test_type="Boundary")
    plan = plan_for(req, [item])

    bundle = parsed_bundle(req, plan, case_payload(req))

    assert bundle.test_cases[0].test_type == item.test_type


def test_canonicalized_priority_equals_planner_exactly():
    req = requirement()
    item = coverage_item(priority="Medium")
    plan = plan_for(req, [item])

    bundle = parsed_bundle(req, plan, case_payload(req))

    assert bundle.test_cases[0].priority == item.priority


def test_parse_generator_response_supports_fallback_exact_coverage_item_without_ref():
    req = requirement()
    item = coverage_item(name="Exact fallback coverage.")
    plan = plan_for(req, [item])
    raw_case = case_payload(req)
    raw_case["traceability"] = {
        "requirement_id": req.id,
        "coverage_item": item.coverage_item,
        "technique_used": "Changed technique",
    }

    bundle = parsed_bundle(req, plan, raw_case)

    assert bundle.status == "SUCCESS"
    assert bundle.test_cases[0].traceability["coverage_item"] == item.coverage_item


def test_parse_generator_response_rejects_invalid_coverage_ref():
    req = requirement()
    plan = plan_for(req)

    bundle = parsed_bundle(req, plan, case_payload(req, coverage_ref="COV_99"))

    assert bundle.status == "FAILED_SCHEMA_VALIDATION"
    assert bundle.test_cases == []


def test_parse_generator_response_rejects_changed_coverage_item_when_ref_missing():
    req = requirement()
    plan = plan_for(req)
    raw_case = case_payload(req)
    raw_case["traceability"] = {
        "requirement_id": req.id,
        "coverage_item": "Different",
        "technique_used": "Functional verification",
    }

    bundle = parsed_bundle(req, plan, raw_case)

    assert bundle.status == "FAILED_SCHEMA_VALIDATION"


def test_parse_generator_response_rejects_missing_traceability():
    req = requirement()
    plan = plan_for(req)
    raw_case = case_payload(req)
    del raw_case["traceability"]

    bundle = parsed_bundle(req, plan, raw_case)

    assert bundle.status == "FAILED_SCHEMA_VALIDATION"


def test_parse_generator_response_rejects_non_dict_traceability():
    req = requirement()
    plan = plan_for(req)
    raw_case = case_payload(req)
    raw_case["traceability"] = []

    bundle = parsed_bundle(req, plan, raw_case)

    assert bundle.status == "FAILED_SCHEMA_VALIDATION"


def test_parse_generator_response_handles_multiple_coverage_refs():
    req = requirement()
    item1 = coverage_item(name="First coverage.", test_type="Positive")
    item2 = coverage_item(name="Second coverage.", test_type="Negative", priority="Medium")
    plan = plan_for(req, [item1, item2])
    case1 = case_payload(req, coverage_ref="COV_1")
    case2 = case_payload(req, coverage_ref="COV_2")
    case2["test_case_id"] = "TC_REQ_1_002"

    result = parse_generator_response(
        response_for(bundle_payload(req, [case1, case2])),
        [req],
        {req.id: plan},
    )[req.id]

    assert [case.traceability["coverage_item"] for case in result.test_cases] == [
        "First coverage.",
        "Second coverage.",
    ]


def test_parse_generator_response_handles_multiple_requirements_in_one_batch():
    req1 = requirement("REQ_1")
    req2 = requirement("REQ_2", "NFR")
    plan1 = plan_for(req1, [coverage_item(name="Coverage one.")])
    plan2 = plan_for(req2, [coverage_item(name="Coverage two.")])

    result = parse_generator_response(
        response_for(
            bundle_payload(req1, [case_payload(req1, coverage_ref="COV_1")]),
            bundle_payload(req2, [case_payload(req2, coverage_ref="COV_1")]),
        ),
        [req1, req2],
        {req1.id: plan1, req2.id: plan2},
    )

    assert result[req1.id].test_cases[0].traceability["coverage_item"] == "Coverage one."
    assert result[req2.id].test_cases[0].traceability["coverage_item"] == "Coverage two."


def test_parsed_output_passes_validation_after_canonicalization():
    req = requirement()
    plan = plan_for(req, [coverage_item(name="Planner exact.")])
    parsed = parse_generator_response(
        response_for(bundle_payload(req, [case_payload(req, coverage_text="Changed")])),
        [req],
        {req.id: plan},
    )

    validated = validate_bundles_against_source_and_plan(parsed, [req], {req.id: plan})

    assert validated[req.id].status == "SUCCESS"


def test_no_unapproved_matching_or_case_normalization_in_generator():
    text = Path("app/services/test_case_generation/generator.py").read_text()

    forbidden = [
        "requirement" + "." + "low" + "er(",
        "." + "low" + "er(",
        "cont" + "ains(",
        "starts" + "with(",
        "fuz" + "zy matching",
        "sim" + "ilarity",
    ]

    for fragment in forbidden:
        assert fragment not in text


def test_validation_py_does_not_need_coverage_ref_for_this_fix():
    text = Path("app/services/test_case_generation/validation.py").read_text()

    assert "coverage_ref" not in text


def test_cache_key_changes_with_generator_prompt_version(monkeypatch):
    req = requirement()
    before = build_cache_key([req], "ctx", "mvp_fast")

    monkeypatch.setattr(cache_module, "TEST_CASE_GENERATOR_PROMPT_VERSION", "generator_v1")

    assert before != build_cache_key([req], "ctx", "mvp_fast")


