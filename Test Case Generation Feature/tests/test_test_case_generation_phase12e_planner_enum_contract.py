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
from app.services.test_case_generation.validation import (
    validate_planner_output_against_requirement,
)


def requirement(requirement_id="REQ_1"):
    return RequirementForTestCase(
        id=requirement_id,
        requirement=f"The system shall process item {requirement_id}.",
        classification_type="FR",
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


def response_for(raw_plan):
    return {"plans": {"1": raw_plan}}


def parsed_plan(raw_plan, req=None):
    req = req or requirement()
    result = parse_planner_response(response_for(raw_plan), [req])
    return result[req.id]


def assert_blocked(plan):
    assert plan.safe_to_generate is False
    assert plan.coverage_items == []
    assert plan.blocking_missing_information[0][: len("Invalid planner output:")] == (
        "Invalid planner output:"
    )


def test_planner_prompt_version_is_planner_v13():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"


def test_generator_prompt_version_is_generator_v8():
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"


def test_build_planner_user_prompt_includes_enum_options():
    prompt = build_planner_user_prompt([requirement()])

    assert '"enum_options":' in prompt


def test_build_planner_user_prompt_includes_tt_positive():
    assert "TT_POSITIVE" in build_planner_user_prompt([requirement()])


def test_build_planner_user_prompt_includes_tt_negative():
    assert "TT_NEGATIVE" in build_planner_user_prompt([requirement()])


def test_build_planner_user_prompt_includes_tt_boundary():
    assert "TT_BOUNDARY" in build_planner_user_prompt([requirement()])


def test_build_planner_system_prompt_instructs_enum_ref_usage():
    prompt = build_planner_system_prompt()

    assert "enum_ref" in prompt
    assert "test_type_ref" in prompt
    assert "priority_ref" in prompt


def test_build_planner_system_prompt_rejects_values_outside_options():
    assert "Never return values outside supplied enum options" in build_planner_system_prompt()


def test_parse_planner_response_accepts_risk_ref_and_canonicalizes_risk_level():
    req = requirement()
    plan = parsed_plan(plan_dict(req, risk_ref="RISK_HIGH", risk_level="Other"), req)

    assert plan.risk_level == "High"


def test_parse_planner_response_accepts_ambiguity_ref_and_canonicalizes_level():
    req = requirement()
    plan = parsed_plan(
        plan_dict(req, ambiguity_ref="AMBIGUITY_MEDIUM", ambiguity_level="Other"),
        req,
    )

    assert plan.ambiguity_level == "Medium"


def test_parse_planner_response_accepts_test_type_ref_and_canonicalizes_test_type():
    req = requirement()
    raw = plan_dict(req, coverage_items=[coverage_item(test_type_ref="TT_NEGATIVE", test_type="Other")])
    plan = parsed_plan(raw, req)

    assert plan.coverage_items[0].test_type == "Negative"


def test_parse_planner_response_accepts_priority_ref_and_canonicalizes_priority():
    req = requirement()
    raw = plan_dict(req, coverage_items=[coverage_item(priority_ref="PRIORITY_LOW", priority="Other")])
    plan = parsed_plan(raw, req)

    assert plan.coverage_items[0].priority == "Low"


def test_parser_canonicalizes_invalid_raw_test_type_when_valid_ref_exists():
    req = requirement()
    raw = plan_dict(req, coverage_items=[coverage_item(test_type_ref="TT_NEGATIVE", test_type="Invalid")])
    plan = parsed_plan(raw, req)

    assert plan.coverage_items[0].test_type == "Negative"


def test_parser_canonicalizes_invalid_raw_priority_when_valid_ref_exists():
    req = requirement()
    raw = plan_dict(req, coverage_items=[coverage_item(priority_ref="PRIORITY_MEDIUM", priority="Invalid")])
    plan = parsed_plan(raw, req)

    assert plan.coverage_items[0].priority == "Medium"


def test_parser_canonicalizes_invalid_raw_risk_level_when_valid_ref_exists():
    req = requirement()
    plan = parsed_plan(plan_dict(req, risk_ref="RISK_LOW", risk_level="Invalid"), req)

    assert plan.risk_level == "Low"


def test_parser_canonicalizes_invalid_raw_ambiguity_level_when_valid_ref_exists():
    req = requirement()
    plan = parsed_plan(
        plan_dict(req, ambiguity_ref="AMBIGUITY_HIGH", ambiguity_level="Invalid"),
        req,
    )

    assert plan.ambiguity_level == "High"


def test_parser_supports_exact_enum_value_fallback_when_refs_missing():
    req = requirement()
    raw = plan_dict(req, risk_level="Medium", ambiguity_level="Low")
    del raw["risk_ref"]
    del raw["ambiguity_ref"]
    raw["coverage_items"] = [
        {
            "coverage_item": "Verify stated behavior.",
            "source_basis": ["The system shall process item REQ_1."],
            "test_type": "Positive",
            "technique_used": "Functional verification",
            "priority": "High",
            "rationale": "Covers planned behavior.",
        }
    ]

    plan = parsed_plan(raw, req)

    assert plan.risk_level == "Medium"
    assert plan.coverage_items[0].test_type == "Positive"
    assert plan.coverage_items[0].priority == "High"


def test_parser_rejects_invalid_test_type_when_ref_missing():
    req = requirement()
    raw = plan_dict(req)
    raw["coverage_items"] = [coverage_item(test_type="Invalid")]
    del raw["coverage_items"][0]["test_type_ref"]

    assert_blocked(parsed_plan(raw, req))


def test_parser_rejects_invalid_priority_when_ref_missing():
    req = requirement()
    raw = plan_dict(req)
    raw["coverage_items"] = [coverage_item(priority="Invalid")]
    del raw["coverage_items"][0]["priority_ref"]

    assert_blocked(parsed_plan(raw, req))


def test_parser_rejects_invalid_risk_level_when_ref_missing():
    req = requirement()
    raw = plan_dict(req, risk_level="Invalid")
    del raw["risk_ref"]

    assert_blocked(parsed_plan(raw, req))


def test_parser_rejects_invalid_ambiguity_level_when_ref_missing():
    req = requirement()
    raw = plan_dict(req, ambiguity_level="Invalid")
    del raw["ambiguity_ref"]

    assert_blocked(parsed_plan(raw, req))


def test_parser_rejects_unknown_test_type_ref():
    req = requirement()
    raw = plan_dict(req, coverage_items=[coverage_item(test_type_ref="TT_UNKNOWN")])

    assert_blocked(parsed_plan(raw, req))


def test_parser_rejects_unknown_priority_ref():
    req = requirement()
    raw = plan_dict(req, coverage_items=[coverage_item(priority_ref="PRIORITY_UNKNOWN")])

    assert_blocked(parsed_plan(raw, req))


def test_parser_rejects_unknown_risk_ref():
    req = requirement()

    assert_blocked(parsed_plan(plan_dict(req, risk_ref="RISK_UNKNOWN"), req))


def test_parser_rejects_unknown_ambiguity_ref():
    req = requirement()

    assert_blocked(parsed_plan(plan_dict(req, ambiguity_ref="AMBIGUITY_UNKNOWN"), req))


def test_parser_rejects_non_string_enum_refs():
    req = requirement()
    raw = plan_dict(req, risk_ref=123)

    assert_blocked(parsed_plan(raw, req))


def test_canonicalized_plan_passes_existing_validation():
    req = requirement()
    raw = plan_dict(
        req,
        risk_ref="RISK_HIGH",
        risk_level="Invalid",
        coverage_items=[coverage_item(test_type_ref="TT_BOUNDARY", test_type="Invalid")],
    )

    plan = parsed_plan(raw, req)

    assert validate_planner_output_against_requirement(plan, req) is plan


def test_parser_does_not_create_coverage_items_in_python():
    req = requirement()
    raw = plan_dict(req, coverage_items=[])

    plan = parsed_plan(raw, req)

    assert plan.coverage_items == []
    assert plan.safe_to_generate is False


def test_parser_does_not_use_unapproved_matching_or_maps():
    text = Path("app/services/test_case_generation/planner.py").read_text()
    forbidden = [
        "." + "low" + "er(",
        "cont" + "ains(",
        "starts" + "with(",
        "fuz" + "zy",
        "sim" + "ilarity",
        "al" + "ias",
    ]

    for fragment in forbidden:
        assert fragment not in text


def test_cache_key_changes_because_planner_prompt_version_changed(monkeypatch):
    req = requirement()
    before = build_cache_key([req], "ctx", "mvp_fast")

    monkeypatch.setattr(cache_module, "TEST_CASE_PROMPT_VERSION", "planner_v2")

    assert before != build_cache_key([req], "ctx", "mvp_fast")


def test_validation_py_unchanged_for_enum_refs():
    text = Path("app/services/test_case_generation/validation.py").read_text()

    assert "test_type_ref" not in text
    assert "risk_ref" not in text


