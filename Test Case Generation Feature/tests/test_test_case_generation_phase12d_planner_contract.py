import json
from pathlib import Path

from app.services.test_case_generation import cache as cache_module
from app.services.test_case_generation.cache import build_cache_key
from app.services.test_case_generation.models import RequirementForTestCase
from app.services.test_case_generation.planner import parse_planner_response
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    build_planner_system_prompt,
    build_planner_user_prompt,
)


def requirement(requirement_id="REQ_1", text=None, requirement_type="FR"):
    return RequirementForTestCase(
        id=requirement_id,
        requirement=text or f"The system shall process item {requirement_id}.",
        classification_type=requirement_type,
    )


def coverage_item(test_type="Positive"):
    return {
        "coverage_item": "Verify stated behavior.",
        "source_basis": ["The system shall process item REQ_1."],
        "test_type": test_type,
        "technique_used": "Functional verification",
        "priority": "High",
        "rationale": "Covers planned behavior.",
    }


def plan_dict(req, **overrides):
    data = {
        "requirement_id": req.id,
        "requirement_text": req.requirement,
        "requirement_type": req.classification_type,
        "testable": True,
        "safe_to_generate": True,
        "risk_level": "Medium",
        "ambiguity_level": "Low",
        "blocking_missing_information": [],
        "missing_information": [],
        "coverage_items": [coverage_item()],
        "recommended_test_case_count": 1,
        "assumptions": [],
    }
    data.update(overrides)
    return data


def blocked_plan_dict(req, **overrides):
    data = plan_dict(
        req,
        testable=False,
        safe_to_generate=False,
        risk_level="Medium",
        ambiguity_level="High",
        blocking_missing_information=["Missing measurable detail"],
        coverage_items=[],
        recommended_test_case_count=0,
    )
    data.update(overrides)
    return data


def response_for(*plans):
    return {"plans": {str(index): plan for index, plan in enumerate(plans, 1)}}


def assert_blocked(plan, reason_prefix=None):
    assert plan.testable is False
    assert plan.safe_to_generate is False
    assert plan.coverage_items == []
    assert plan.recommended_test_case_count == 0
    if reason_prefix:
        reason = plan.blocking_missing_information[0]
        assert reason[: len(reason_prefix)] == reason_prefix


def test_planner_prompt_version_is_planner_v13():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"


def test_generator_prompt_version_is_generator_v8():
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"


def test_build_planner_user_prompt_includes_json_input_payload():
    req = requirement()

    prompt = build_planner_user_prompt([req], "Context")

    assert "Input:" in prompt
    assert '"requirements":[{' in prompt


def test_build_planner_user_prompt_includes_index_string_one():
    req = requirement()

    prompt = build_planner_user_prompt([req])

    assert '"index":"1"' in prompt


def test_build_planner_user_prompt_preserves_exact_requirement_text():
    text = "The system shall show invoice details including invoice date."
    req = requirement(text=text)

    prompt = build_planner_user_prompt([req])

    assert text in prompt


def test_build_planner_system_prompt_says_return_exactly_one_json_object():
    assert "Return exactly one JSON object" in build_planner_system_prompt()


def test_build_planner_system_prompt_says_no_markdown_code_fences_explanation():
    prompt = build_planner_system_prompt()

    assert "Do not include markdown" in prompt
    assert "code fences" in prompt
    assert "explanation text" in prompt


def test_build_planner_system_prompt_says_include_one_plan_per_input_index():
    assert "Include one plan per input index" in build_planner_system_prompt()


def test_parse_planner_response_accepts_preferred_plans_dict():
    req = requirement()

    result = parse_planner_response(response_for(plan_dict(req)), [req])

    assert result[req.id].safe_to_generate is True


def test_parse_planner_response_accepts_plans_list():
    req = requirement()

    result = parse_planner_response({"plans": [plan_dict(req)]}, [req])

    assert result[req.id].requirement_id == req.id


def test_parse_planner_response_accepts_top_level_list():
    req = requirement()

    result = parse_planner_response([plan_dict(req)], [req])

    assert result[req.id].requirement_text == req.requirement


def test_parse_planner_response_accepts_single_top_level_plan_for_one_requirement():
    req = requirement()

    result = parse_planner_response(plan_dict(req), [req])

    assert result[req.id].requirement_type == req.classification_type


def test_parse_planner_response_rejects_single_top_level_plan_for_multiple_requirements():
    reqs = [requirement("REQ_1"), requirement("REQ_2")]

    result = parse_planner_response(plan_dict(reqs[0]), reqs)

    assert all(not plan.safe_to_generate for plan in result.values())
    assert all(
        plan.blocking_missing_information
        == ["Planner output could not be parsed. Retry generation."]
        for plan in result.values()
    )


def test_parse_planner_response_rejects_missing_plans_envelope():
    req = requirement()

    result = parse_planner_response({"metadata": {}}, [req])

    assert_blocked(result[req.id])
    assert result[req.id].blocking_missing_information == [
        "Planner output could not be parsed. Retry generation."
    ]


def test_parse_planner_response_rejects_plan_missing_source_identity():
    req = requirement()
    raw_plan = plan_dict(req)
    del raw_plan["requirement_id"]

    result = parse_planner_response(response_for(raw_plan), [req])

    assert_blocked(result[req.id], "Invalid planner output:")


def test_parse_planner_response_rejects_mismatched_requirement_id():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, requirement_id="OTHER")),
        [req],
    )

    assert_blocked(result[req.id], "Invalid planner output:")


def test_parse_planner_response_rejects_mismatched_requirement_text():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, requirement_text="Different text.")),
        [req],
    )

    assert_blocked(result[req.id], "Invalid planner output:")


def test_parse_planner_response_rejects_invalid_risk_level():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, risk_level="Critical")),
        [req],
    )

    assert_blocked(result[req.id], "Invalid planner output:")


def test_parse_planner_response_rejects_invalid_test_type_inside_coverage_item():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, coverage_items=[coverage_item(test_type="Other")])),
        [req],
    )

    assert_blocked(result[req.id], "Invalid planner output:")


def test_malformed_whole_response_still_returns_malformed_reason():
    req = requirement()

    result = parse_planner_response("not json", [req])

    assert result[req.id].blocking_missing_information == [
        "Planner output could not be parsed. Retry generation."
    ]


def test_invalid_individual_plan_returns_invalid_reason_prefix():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, recommended_test_case_count=0)),
        [req],
    )

    assert_blocked(result[req.id], "Invalid planner output:")


def test_list_variant_preserves_requirement_order_by_index():
    reqs = [requirement("REQ_1"), requirement("REQ_2", requirement_type="NFR")]

    result = parse_planner_response(
        [plan_dict(reqs[0]), plan_dict(reqs[1])],
        reqs,
    )

    assert result["REQ_1"].requirement_id == "REQ_1"
    assert result["REQ_2"].requirement_id == "REQ_2"


def test_missing_second_plan_in_list_blocks_only_second_requirement():
    reqs = [requirement("REQ_1"), requirement("REQ_2")]

    result = parse_planner_response({"plans": [plan_dict(reqs[0])]}, reqs)

    assert result["REQ_1"].safe_to_generate is True
    assert_blocked(result["REQ_2"])
    assert result["REQ_2"].blocking_missing_information == [
        "Planner response missing requirement plan"
    ]


def test_blocked_planner_output_with_zero_count_still_parses():
    req = requirement()

    result = parse_planner_response(response_for(blocked_plan_dict(req)), [req])

    assert result[req.id].safe_to_generate is False
    assert result[req.id].recommended_test_case_count == 0


def test_blocked_planner_output_with_nonzero_count_is_rejected():
    req = requirement()

    result = parse_planner_response(
        response_for(blocked_plan_dict(req, recommended_test_case_count=1)),
        [req],
    )

    assert_blocked(result[req.id], "Invalid planner output:")


def test_parser_does_not_create_coverage_items_in_python():
    req = requirement()

    result = parse_planner_response(
        response_for(plan_dict(req, coverage_items=[])),
        [req],
    )

    assert result[req.id].coverage_items == []
    assert result[req.id].safe_to_generate is False


def test_parser_does_not_use_case_normalization_or_partial_matching():
    text = Path("app/services/test_case_generation/planner.py").read_text()
    forbidden = [
        "." + "low" + "er(",
        "cont" + "ains(",
        "starts" + "with(",
        "fuz" + "zy",
        "sim" + "ilarity",
    ]

    for fragment in forbidden:
        assert fragment not in text


def test_cache_key_changes_because_planner_prompt_version_changed(monkeypatch):
    req = requirement()
    before = build_cache_key([req], "ctx", "mvp_fast")

    monkeypatch.setattr(cache_module, "TEST_CASE_PROMPT_VERSION", "planner_v1")

    assert before != build_cache_key([req], "ctx", "mvp_fast")


def test_validation_py_does_not_contain_phase12d_planner_helpers():
    text = Path("app/services/test_case_generation/validation.py").read_text()

    assert "_normalize_plans_container" not in text
    assert "planner_v2" not in text


