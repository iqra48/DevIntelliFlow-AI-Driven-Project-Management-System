from pathlib import Path

import pytest

from app.services.test_case_generation.models import (
    CoverageItem,
    PlannerOutput,
    RequirementForTestCase,
    TestCase as CaseModel,
    TestCaseBundle as BundleModel,
    TestStep as StepModel,
)
from app.services.test_case_generation.validation import (
    validate_bundle_against_plan,
    validate_bundle_against_source_and_plan,
    validate_bundle_structure,
    validate_bundles_against_source_and_plan,
)


@pytest.fixture
def requirement():
    return RequirementForTestCase(
        id="REQ_1",
        requirement="The system shall process submitted records.",
        classification_type="FR",
    )


@pytest.fixture
def coverage_item():
    return CoverageItem(
        coverage_item="Verify stated behavior.",
        source_basis=["The system shall process item REQ_1."],
        test_type="Positive",
        technique_used="Functional verification",
        priority="High",
        rationale="Covers the planned behavior.",
    )


@pytest.fixture
def plan(requirement, coverage_item):
    return PlannerOutput(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        testable=True,
        safe_to_generate=True,
        risk_level="Medium",
        ambiguity_level="Low",
        blocking_missing_information=[],
        missing_information=[],
        coverage_items=[coverage_item],
        recommended_test_case_count=2,
        assumptions=[],
    )


@pytest.fixture
def test_case(requirement, coverage_item):
    return CaseModel(
        test_case_id="TC_REQ_1_001",
        requirement_id=requirement.id,
        title="Verify submitted records are processed",
        objective="Confirm the stated requirement is satisfied.",
        test_type=coverage_item.test_type,
        technique_used=coverage_item.technique_used,
        priority=coverage_item.priority,
        preconditions=["System is available."],
        test_data={},
        steps=[
            StepModel(
                step_number=1,
                action="Perform the stated operation.",
                expected_result="The stated outcome is observed.",
            )
        ],
        expected_result="The requirement is satisfied.",
        assumption_required=False,
        assumptions=[],
        source_basis=list(coverage_item.source_basis),
        traceability={
            "requirement_id": requirement.id,
            "coverage_item": coverage_item.coverage_item,
            "technique_used": coverage_item.technique_used,
        },
    )


@pytest.fixture
def bundle(requirement, test_case):
    return BundleModel(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        status="SUCCESS",
        test_cases=[test_case],
        missing_information=[],
        assumptions=[],
        warnings=[],
        reason=None,
    )


def clone_case(test_case, **overrides):
    data = test_case.to_dict()
    data.update(overrides)
    data["steps"] = [
        step if isinstance(step, StepModel) else StepModel.from_dict(step)
        for step in data["steps"]
    ]
    return CaseModel.from_dict(data)


def clone_bundle(bundle, **overrides):
    data = bundle.to_dict()
    data.update(overrides)
    data["test_cases"] = [
        case if isinstance(case, CaseModel) else CaseModel.from_dict(case)
        for case in data["test_cases"]
    ]
    return BundleModel.from_dict(data)


def failed(result):
    assert result.status == "FAILED_SCHEMA_VALIDATION"
    assert result.test_cases == []
    assert result.reason


def test_valid_bundle_passes_unchanged(bundle, requirement):
    assert validate_bundle_structure(bundle, requirement) is bundle


def test_mismatched_bundle_requirement_id_returns_failed(bundle, requirement):
    result = validate_bundle_structure(
        clone_bundle(bundle, requirement_id="OTHER"),
        requirement,
    )
    failed(result)


def test_mismatched_bundle_requirement_text_returns_failed(bundle, requirement):
    result = validate_bundle_structure(
        clone_bundle(bundle, requirement_text="Different text."),
        requirement,
    )
    failed(result)


def test_mismatched_bundle_requirement_type_returns_failed(bundle, requirement):
    result = validate_bundle_structure(
        clone_bundle(bundle, requirement_type="NFR"),
        requirement,
    )
    failed(result)


def test_invalid_bundle_status_returns_failed(bundle, requirement):
    result = validate_bundle_structure(
        clone_bundle(bundle, status="UNKNOWN"),
        requirement,
    )
    failed(result)


def test_invalid_test_case_requirement_id_is_discarded(bundle, requirement, test_case):
    bad = clone_case(test_case, requirement_id="OTHER")
    result = validate_bundle_structure(clone_bundle(bundle, test_cases=[bad]), requirement)
    failed(result)


def test_empty_test_case_id_is_discarded(bundle, requirement, test_case):
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, test_case_id=" ")]),
        requirement,
    )
    failed(result)


def test_empty_title_is_discarded(bundle, requirement, test_case):
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, title=" ")]),
        requirement,
    )
    failed(result)


def test_empty_objective_is_discarded(bundle, requirement, test_case):
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, objective=" ")]),
        requirement,
    )
    failed(result)


def test_invalid_test_type_is_discarded(bundle, requirement, test_case):
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, test_type="Other")]),
        requirement,
    )
    failed(result)


def test_invalid_priority_is_discarded(bundle, requirement, test_case):
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, priority="Urgent")]),
        requirement,
    )
    failed(result)


def test_preconditions_not_list_of_strings_is_discarded(bundle, requirement, test_case):
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, preconditions=[1])]),
        requirement,
    )
    failed(result)


def test_test_data_not_dict_is_discarded(bundle, requirement, test_case):
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, test_data=[])]),
        requirement,
    )
    failed(result)


def test_empty_steps_is_discarded(bundle, requirement, test_case):
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, steps=[])]),
        requirement,
    )
    failed(result)


def test_invalid_step_number_is_discarded(bundle, requirement, test_case):
    bad_step = StepModel(step_number=0, action="Act", expected_result="Observe")
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, steps=[bad_step])]),
        requirement,
    )
    failed(result)


def test_empty_step_action_is_discarded(bundle, requirement, test_case):
    bad_step = StepModel(step_number=1, action=" ", expected_result="Observe")
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, steps=[bad_step])]),
        requirement,
    )
    failed(result)


def test_empty_step_expected_result_is_discarded(bundle, requirement, test_case):
    bad_step = StepModel(step_number=1, action="Act", expected_result=" ")
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, steps=[bad_step])]),
        requirement,
    )
    failed(result)


def test_empty_final_expected_result_is_discarded(bundle, requirement, test_case):
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, expected_result=" ")]),
        requirement,
    )
    failed(result)


def test_assumption_required_not_bool_is_discarded(bundle, requirement, test_case):
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, assumption_required="no")]),
        requirement,
    )
    failed(result)


def test_assumptions_not_list_of_strings_is_discarded(bundle, requirement, test_case):
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, assumptions=[1])]),
        requirement,
    )
    failed(result)


def test_traceability_missing_requirement_id_is_discarded(bundle, requirement, test_case):
    traceability = dict(test_case.traceability)
    del traceability["requirement_id"]
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[clone_case(test_case, traceability=traceability)]),
        requirement,
    )
    failed(result)


def test_duplicate_test_case_id_discards_duplicate_and_marks_needs_review(
    bundle,
    requirement,
    test_case,
):
    duplicate = clone_case(test_case)
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[test_case, duplicate]),
        requirement,
    )
    assert result.status == "NEEDS_REVIEW"
    assert len(result.test_cases) == 1


def test_one_bad_test_case_discarded_while_valid_one_remains(
    bundle,
    requirement,
    test_case,
):
    bad = clone_case(test_case, title=" ")
    result = validate_bundle_structure(
        clone_bundle(bundle, test_cases=[test_case, bad]),
        requirement,
    )
    assert result.status == "NEEDS_REVIEW"
    assert len(result.test_cases) == 1


def test_all_bad_test_cases_returns_failed(bundle, requirement, test_case):
    bad = clone_case(test_case, title=" ")
    result = validate_bundle_structure(clone_bundle(bundle, test_cases=[bad]), requirement)
    failed(result)


def test_valid_bundle_matches_plan_and_passes(bundle, plan):
    assert validate_bundle_against_plan(bundle, plan) is bundle


def test_plan_safe_to_generate_false_returns_failed(bundle, plan):
    blocked = PlannerOutput(
        **{**plan.to_dict(), "safe_to_generate": False, "recommended_test_case_count": 0}
    )
    result = validate_bundle_against_plan(bundle, blocked)
    failed(result)


def test_coverage_item_not_in_planner_output_is_discarded(bundle, plan, test_case):
    traceability = dict(test_case.traceability)
    traceability["coverage_item"] = "Unplanned coverage"
    result = validate_bundle_against_plan(
        clone_bundle(bundle, test_cases=[clone_case(test_case, traceability=traceability)]),
        plan,
    )
    failed(result)


def test_test_type_different_from_planner_coverage_item_is_discarded(
    bundle,
    plan,
    test_case,
):
    result = validate_bundle_against_plan(
        clone_bundle(bundle, test_cases=[clone_case(test_case, test_type="Negative")]),
        plan,
    )
    failed(result)


def test_technique_used_different_from_planner_coverage_item_is_discarded(
    bundle,
    plan,
    test_case,
):
    result = validate_bundle_against_plan(
        clone_bundle(bundle, test_cases=[clone_case(test_case, technique_used="Other technique")]),
        plan,
    )
    failed(result)


def test_traceability_technique_used_different_from_planner_is_discarded(
    bundle,
    plan,
    test_case,
):
    traceability = dict(test_case.traceability)
    traceability["technique_used"] = "Other technique"
    result = validate_bundle_against_plan(
        clone_bundle(bundle, test_cases=[clone_case(test_case, traceability=traceability)]),
        plan,
    )
    failed(result)


def test_generated_count_above_recommended_count_trims_extras_and_marks_needs_review(
    bundle,
    plan,
    test_case,
):
    extra = clone_case(test_case, test_case_id="TC_REQ_1_002")
    third = clone_case(test_case, test_case_id="TC_REQ_1_003")
    result = validate_bundle_against_plan(
        clone_bundle(bundle, test_cases=[test_case, extra, third]),
        plan,
    )
    assert result.status == "NEEDS_REVIEW"
    assert len(result.test_cases) == 2


def test_all_consistency_invalid_cases_returns_failed(bundle, plan, test_case):
    result = validate_bundle_against_plan(
        clone_bundle(bundle, test_cases=[clone_case(test_case, test_type="Negative")]),
        plan,
    )
    failed(result)


def test_validate_bundles_against_source_and_plan_validates_multiple_bundles(
    requirement,
    plan,
    bundle,
    coverage_item,
):
    req2 = RequirementForTestCase("REQ_2", "The system shall archive records.", "NFR")
    plan2 = PlannerOutput(
        requirement_id=req2.id,
        requirement_text=req2.requirement,
        requirement_type=req2.classification_type,
        testable=True,
        safe_to_generate=True,
        risk_level="Medium",
        ambiguity_level="Low",
        blocking_missing_information=[],
        missing_information=[],
        coverage_items=[coverage_item],
        recommended_test_case_count=1,
        assumptions=[],
    )
    case2 = clone_case(
        bundle.test_cases[0],
        test_case_id="TC_REQ_2_001",
        requirement_id=req2.id,
        traceability={
            "requirement_id": req2.id,
            "coverage_item": coverage_item.coverage_item,
            "technique_used": coverage_item.technique_used,
        },
    )
    bundle2 = BundleModel(
        req2.id,
        req2.requirement,
        req2.classification_type,
        "SUCCESS",
        [case2],
        [],
        [],
        [],
    )

    result = validate_bundles_against_source_and_plan(
        {requirement.id: bundle, req2.id: bundle2},
        [requirement, req2],
        {requirement.id: plan, req2.id: plan2},
    )

    assert result[requirement.id].status == "SUCCESS"
    assert result[req2.id].status == "SUCCESS"


def test_missing_bundle_returns_failed(requirement, plan):
    result = validate_bundles_against_source_and_plan(
        {},
        [requirement],
        {requirement.id: plan},
    )
    failed(result[requirement.id])


def test_missing_plan_returns_failed(requirement, bundle):
    result = validate_bundles_against_source_and_plan(
        {requirement.id: bundle},
        [requirement],
        {},
    )
    failed(result[requirement.id])


def test_no_text_content_inspection_is_needed(requirement, plan, bundle):
    result = validate_bundle_against_source_and_plan(bundle, requirement, plan)
    assert result.status == "SUCCESS"


def test_no_llm_imports_or_calls_are_used_by_validation_tests():
    validation_text = Path(
        "app/services/test_case_generation/validation.py"
    ).read_text()
    assert "call_llm" not in validation_text
    assert "guarded_llm_call" not in validation_text

