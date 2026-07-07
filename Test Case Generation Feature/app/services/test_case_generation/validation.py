from app.services.test_case_generation.models import (
    ALLOWED_AMBIGUITY_LEVELS,
    ALLOWED_MODES,
    ALLOWED_PRIORITIES,
    ALLOWED_REQUIREMENT_TYPES,
    ALLOWED_RISK_LEVELS,
    ALLOWED_STATUSES,
    ALLOWED_TEST_TYPES,
    MODE_CONFIG,
    CoverageItem,
    PlannerOutput,
    RequirementForTestCase,
    TestCase,
    TestCaseBundle,
    TestStep,
)


class TestCaseValidationError(ValueError):
    __test__ = False

    pass


def _validate_enum(value: str, allowed: set[str], field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TestCaseValidationError(f"{field_name} must be a non-empty string")

    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise TestCaseValidationError(
            f"{field_name} must be one of: {allowed_values}"
        )

    return value


def validate_mode(mode: str) -> str:
    return _validate_enum(mode, ALLOWED_MODES, "mode")


def validate_status(status: str) -> str:
    return _validate_enum(status, ALLOWED_STATUSES, "status")


def validate_priority(priority: str) -> str:
    return _validate_enum(priority, ALLOWED_PRIORITIES, "priority")


def validate_test_type(test_type: str) -> str:
    return _validate_enum(test_type, ALLOWED_TEST_TYPES, "test_type")


def validate_risk_level(risk_level: str) -> str:
    return _validate_enum(risk_level, ALLOWED_RISK_LEVELS, "risk_level")


def validate_ambiguity_level(ambiguity_level: str) -> str:
    return _validate_enum(
        ambiguity_level,
        ALLOWED_AMBIGUITY_LEVELS,
        "ambiguity_level",
    )


def normalize_requirement(raw: dict) -> RequirementForTestCase:
    """
    Convert one raw requirement dict into RequirementForTestCase.
    Structural validation only.
    No semantic keyword checks.
    """
    if not isinstance(raw, dict):
        raise TestCaseValidationError("requirement item must be a dict")

    if "id" not in raw:
        raise TestCaseValidationError("id is required")
    requirement_id = raw["id"]
    if not isinstance(requirement_id, str) or not requirement_id.strip():
        raise TestCaseValidationError("id must be a non-empty string")

    if "requirement" not in raw:
        raise TestCaseValidationError("requirement is required")
    requirement_text = raw["requirement"]
    if not isinstance(requirement_text, str) or not requirement_text.strip():
        raise TestCaseValidationError("requirement must be a non-empty string")

    if "classification_type" not in raw:
        raise TestCaseValidationError("classification_type is required")
    classification_type = raw["classification_type"]
    if not isinstance(classification_type, str) or not classification_type:
        raise TestCaseValidationError(
            "classification_type must be a non-empty string"
        )
    if classification_type not in ALLOWED_REQUIREMENT_TYPES:
        raise TestCaseValidationError("classification_type must be FR or NFR")

    return RequirementForTestCase(
        id=requirement_id.strip(),
        requirement=requirement_text.strip(),
        classification_type=classification_type,
    )


def normalize_requirements(
    raw_requirements: list[dict],
    mode: str = "mvp_fast",
) -> list[RequirementForTestCase]:
    """
    Validate and normalize a request list.
    """
    mode = validate_mode(mode)

    if not isinstance(raw_requirements, list) or not raw_requirements:
        raise TestCaseValidationError("raw_requirements must be a non-empty list")

    max_requirements = MODE_CONFIG[mode]["max_requirements"]
    if len(raw_requirements) > max_requirements:
        raise TestCaseValidationError(
            f"mode {mode} allows at most {max_requirements} requirements"
        )

    normalized = [normalize_requirement(raw) for raw in raw_requirements]

    seen_ids = set()
    for requirement in normalized:
        if requirement.id in seen_ids:
            raise TestCaseValidationError(
                f"duplicate requirement id: {requirement.id}"
            )
        seen_ids.add(requirement.id)

    return normalized


def chunk_requirements(
    requirements: list[RequirementForTestCase],
    mode: str,
) -> list[list[RequirementForTestCase]]:
    """
    Chunk using MODE_CONFIG[mode]["chunk_size"].
    """
    mode = validate_mode(mode)

    if not isinstance(requirements, list):
        raise TestCaseValidationError("requirements must be a list")

    chunk_size = MODE_CONFIG[mode]["chunk_size"]
    return [
        requirements[index : index + chunk_size]
        for index in range(0, len(requirements), chunk_size)
    ]


def validate_planner_output_against_requirement(
    plan: PlannerOutput,
    requirement: RequirementForTestCase,
    mode: str = "mvp_fast",
) -> PlannerOutput:
    """
    Structural planner validation.
    No semantic keyword checks.
    """
    mode = validate_mode(mode)

    if plan.requirement_id != requirement.id:
        raise TestCaseValidationError("requirement_id does not match source")
    if plan.requirement_text != requirement.requirement:
        raise TestCaseValidationError("requirement_text does not match source")
    if plan.requirement_type != requirement.classification_type:
        raise TestCaseValidationError("requirement_type does not match source")

    if not isinstance(plan.testable, bool):
        raise TestCaseValidationError("testable must be bool")
    if not isinstance(plan.safe_to_generate, bool):
        raise TestCaseValidationError("safe_to_generate must be bool")

    validate_risk_level(plan.risk_level)
    validate_ambiguity_level(plan.ambiguity_level)

    for field_name in (
        "blocking_missing_information",
        "missing_information",
        "assumptions",
    ):
        value = getattr(plan, field_name)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise TestCaseValidationError(f"{field_name} must be list[str]")

    if not isinstance(plan.coverage_items, list):
        raise TestCaseValidationError("coverage_items must be a list")

    for item in plan.coverage_items:
        if not isinstance(item.coverage_item, str) or not item.coverage_item.strip():
            raise TestCaseValidationError("coverage_item must be a non-empty string")
        validate_test_type(item.test_type)
        if not isinstance(item.technique_used, str) or not item.technique_used.strip():
            raise TestCaseValidationError("technique_used must be a non-empty string")
        validate_priority(item.priority)
        if not isinstance(item.rationale, str) or not item.rationale.strip():
            raise TestCaseValidationError("rationale must be a non-empty string")
        _validate_list_of_strings(item.source_basis, "source_basis", allow_empty=False)
        if not all(item.strip() for item in item.source_basis):
            raise TestCaseValidationError("source_basis must contain only non-empty strings")

    if not isinstance(plan.recommended_test_case_count, int):
        raise TestCaseValidationError("recommended_test_case_count must be int")

    max_count = MODE_CONFIG[mode]["max_test_cases_per_requirement"]
    if plan.safe_to_generate:
        if not plan.coverage_items:
            raise TestCaseValidationError(
                "coverage_items must not be empty when safe_to_generate is true"
            )
        if not 1 <= plan.recommended_test_case_count <= max_count:
            raise TestCaseValidationError(
                "recommended_test_case_count must be between 1 and mode max"
            )
    elif plan.recommended_test_case_count != 0:
        raise TestCaseValidationError(
            "recommended_test_case_count must be 0 when safe_to_generate is false"
        )

    return plan


def _is_non_empty_string(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_list_of_strings(
    value,
    field_name: str,
    allow_empty: bool = True,
) -> list[str]:
    """
    Validate list[str].
    Return the original list if valid.
    """
    if not isinstance(value, list):
        raise TestCaseValidationError(f"{field_name} must be a list")
    if not allow_empty and not value:
        raise TestCaseValidationError(f"{field_name} must not be empty")
    if not all(isinstance(item, str) for item in value):
        raise TestCaseValidationError(f"{field_name} must contain only strings")
    return value


def _validate_traceability_dict(value) -> dict[str, str]:
    """
    Validate traceability is dict[str, str] with required keys.
    """
    if not isinstance(value, dict):
        raise TestCaseValidationError("traceability must be a dict")
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise TestCaseValidationError("traceability must be dict[str, str]")

    for field_name in ("requirement_id", "coverage_item", "technique_used"):
        if field_name not in value:
            raise TestCaseValidationError(f"traceability missing {field_name}")
        if not _is_non_empty_string(value[field_name]):
            raise TestCaseValidationError(f"traceability {field_name} must be non-empty")

    return value


def make_validation_failed_bundle(
    requirement: RequirementForTestCase,
    reason: str,
    plan: PlannerOutput | None = None,
    warnings: list[str] | None = None,
) -> TestCaseBundle:
    """
    Create FAILED_SCHEMA_VALIDATION fallback bundle.
    """
    merged_warnings = list(warnings or [])
    if reason not in merged_warnings:
        merged_warnings.append(reason)

    return TestCaseBundle(
        requirement_id=requirement.id,
        requirement_text=requirement.requirement,
        requirement_type=requirement.classification_type,
        status="FAILED_SCHEMA_VALIDATION",
        test_cases=[],
        missing_information=list(plan.missing_information) if plan else [],
        assumptions=list(plan.assumptions) if plan else [],
        warnings=merged_warnings,
        reason=reason,
    )


def validate_test_step(step: TestStep) -> TestStep:
    """
    Structural validation for one step.
    """
    if not isinstance(step, TestStep):
        raise TestCaseValidationError("step must be TestStep")
    if not isinstance(step.step_number, int) or step.step_number < 1:
        raise TestCaseValidationError("step_number must be int and >= 1")
    if not _is_non_empty_string(step.action):
        raise TestCaseValidationError("action must be a non-empty string")
    if not _is_non_empty_string(step.expected_result):
        raise TestCaseValidationError("expected_result must be a non-empty string")
    return step


def validate_test_case_against_requirement(
    test_case: TestCase,
    requirement: RequirementForTestCase,
) -> TestCase:
    """
    Structural validation for one generated test case.
    No planner consistency here.
    """
    if not isinstance(test_case, TestCase):
        raise TestCaseValidationError("test_case must be TestCase")
    if not _is_non_empty_string(test_case.test_case_id):
        raise TestCaseValidationError("test_case_id must be a non-empty string")
    if test_case.requirement_id != requirement.id:
        raise TestCaseValidationError("test_case requirement_id does not match source")
    if not _is_non_empty_string(test_case.title):
        raise TestCaseValidationError("title must be a non-empty string")
    if not _is_non_empty_string(test_case.objective):
        raise TestCaseValidationError("objective must be a non-empty string")
    validate_test_type(test_case.test_type)
    if not _is_non_empty_string(test_case.technique_used):
        raise TestCaseValidationError("technique_used must be a non-empty string")
    validate_priority(test_case.priority)
    _validate_list_of_strings(test_case.preconditions, "preconditions")
    if not isinstance(test_case.test_data, dict):
        raise TestCaseValidationError("test_data must be a dict")
    if not isinstance(test_case.steps, list) or not test_case.steps:
        raise TestCaseValidationError("steps must be a non-empty list")
    for step in test_case.steps:
        validate_test_step(step)
    if not _is_non_empty_string(test_case.expected_result):
        raise TestCaseValidationError("expected_result must be a non-empty string")
    if not isinstance(test_case.assumption_required, bool):
        raise TestCaseValidationError("assumption_required must be bool")
    _validate_list_of_strings(test_case.assumptions, "assumptions")
    _validate_list_of_strings(test_case.source_basis, "source_basis", allow_empty=False)
    if not all(item.strip() for item in test_case.source_basis):
        raise TestCaseValidationError("source_basis must contain only non-empty strings")
    traceability = _validate_traceability_dict(test_case.traceability)
    if traceability["requirement_id"] != requirement.id:
        raise TestCaseValidationError("traceability requirement_id does not match source")
    return test_case


def validate_bundle_structure(
    bundle: TestCaseBundle,
    requirement: RequirementForTestCase,
) -> TestCaseBundle:
    """
    Validate bundle source identity and structurally validate each test case.
    Invalid individual test cases are discarded.
    """
    if not isinstance(bundle, TestCaseBundle):
        return make_validation_failed_bundle(
            requirement,
            "Bundle must be TestCaseBundle",
        )

    warnings = list(bundle.warnings) if isinstance(bundle.warnings, list) else []

    identity_errors = []
    if bundle.requirement_id != requirement.id:
        identity_errors.append("bundle requirement_id does not match source")
    if bundle.requirement_text != requirement.requirement:
        identity_errors.append("bundle requirement_text does not match source")
    if bundle.requirement_type != requirement.classification_type:
        identity_errors.append("bundle requirement_type does not match source")
    try:
        validate_status(bundle.status)
    except Exception as exc:
        identity_errors.append(str(exc))

    for field_name in ("missing_information", "assumptions", "warnings"):
        try:
            _validate_list_of_strings(getattr(bundle, field_name), field_name)
        except Exception as exc:
            identity_errors.append(str(exc))

    if not isinstance(bundle.test_cases, list):
        identity_errors.append("test_cases must be a list")

    if identity_errors:
        return make_validation_failed_bundle(
            requirement,
            "Bundle failed structural validation",
            warnings=warnings + identity_errors,
        )

    valid_cases: list[TestCase] = []
    seen_ids: set[str] = set()
    discard_reasons: list[str] = []

    for index, test_case in enumerate(bundle.test_cases, 1):
        try:
            validated = validate_test_case_against_requirement(test_case, requirement)
            if validated.test_case_id in seen_ids:
                discard_reasons.append(
                    f"test case {index} discarded: duplicate test_case_id"
                )
                continue
            seen_ids.add(validated.test_case_id)
            valid_cases.append(validated)
        except Exception as exc:
            discard_reasons.append(f"test case {index} discarded: {exc}")

    if not valid_cases:
        return TestCaseBundle(
            requirement_id=requirement.id,
            requirement_text=requirement.requirement,
            requirement_type=requirement.classification_type,
            status="FAILED_SCHEMA_VALIDATION",
            test_cases=[],
            missing_information=list(bundle.missing_information),
            assumptions=list(bundle.assumptions),
            warnings=warnings + discard_reasons,
            reason="All generated test cases failed structural validation",
        )

    if discard_reasons:
        return TestCaseBundle(
            requirement_id=bundle.requirement_id,
            requirement_text=bundle.requirement_text,
            requirement_type=bundle.requirement_type,
            status="NEEDS_REVIEW",
            test_cases=valid_cases,
            missing_information=list(bundle.missing_information),
            assumptions=list(bundle.assumptions),
            warnings=warnings + discard_reasons,
            reason=bundle.reason,
        )

    return bundle


def _failed_bundle_from_plan(
    plan: PlannerOutput,
    reason: str,
    warnings: list[str] | None = None,
) -> TestCaseBundle:
    requirement = RequirementForTestCase(
        id=plan.requirement_id,
        requirement=plan.requirement_text,
        classification_type=plan.requirement_type,
    )
    return make_validation_failed_bundle(requirement, reason, plan, warnings)


def validate_bundle_against_plan(
    bundle: TestCaseBundle,
    plan: PlannerOutput,
) -> TestCaseBundle:
    """
    Planner-generator consistency validation.
    Invalid individual test cases are discarded.
    """
    warnings = list(bundle.warnings)

    identity_errors = []
    if bundle.requirement_id != plan.requirement_id:
        identity_errors.append("bundle requirement_id does not match plan")
    if bundle.requirement_text != plan.requirement_text:
        identity_errors.append("bundle requirement_text does not match plan")
    if bundle.requirement_type != plan.requirement_type:
        identity_errors.append("bundle requirement_type does not match plan")
    if identity_errors:
        return _failed_bundle_from_plan(
            plan,
            "Bundle failed planner consistency validation",
            warnings + identity_errors,
        )

    if not plan.safe_to_generate:
        return _failed_bundle_from_plan(
            plan,
            "Planner output is not safe to generate",
            warnings,
        )

    test_cases = list(bundle.test_cases)
    if len(test_cases) > plan.recommended_test_case_count:
        test_cases = test_cases[: plan.recommended_test_case_count]
        warnings.append(
            "Generated test cases exceeded planner recommended count; extra cases discarded"
        )

    allowed: dict[str, CoverageItem] = {
        item.coverage_item: item for item in plan.coverage_items
    }

    valid_cases: list[TestCase] = []
    discard_reasons: list[str] = []
    for index, test_case in enumerate(test_cases, 1):
        try:
            traceability = _validate_traceability_dict(test_case.traceability)
            coverage_name = traceability["coverage_item"]
            planned_item = allowed.get(coverage_name)
            if not planned_item:
                raise TestCaseValidationError("coverage_item is not in planner output")
            if test_case.test_type != planned_item.test_type:
                raise TestCaseValidationError("test_type does not match planner coverage")
            if test_case.technique_used != planned_item.technique_used:
                raise TestCaseValidationError("technique_used does not match planner coverage")
            if traceability["technique_used"] != planned_item.technique_used:
                raise TestCaseValidationError(
                    "traceability technique_used does not match planner coverage"
                )
            if test_case.source_basis != planned_item.source_basis:
                raise TestCaseValidationError("source_basis does not match planner coverage")
            valid_cases.append(test_case)
        except Exception as exc:
            discard_reasons.append(f"test case {index} discarded: {exc}")

    if not valid_cases:
        return _failed_bundle_from_plan(
            plan,
            "All generated test cases failed planner consistency validation",
            warnings + discard_reasons,
        )

    if discard_reasons or len(test_cases) != len(bundle.test_cases):
        return TestCaseBundle(
            requirement_id=bundle.requirement_id,
            requirement_text=bundle.requirement_text,
            requirement_type=bundle.requirement_type,
            status="NEEDS_REVIEW",
            test_cases=valid_cases,
            missing_information=list(bundle.missing_information),
            assumptions=list(bundle.assumptions),
            warnings=warnings + discard_reasons,
            reason=bundle.reason,
        )

    return bundle


def validate_bundle_against_source_and_plan(
    bundle: TestCaseBundle,
    requirement: RequirementForTestCase,
    plan: PlannerOutput,
) -> TestCaseBundle:
    """
    Run structural validation first, then plan-consistency validation.
    """
    structurally_valid = validate_bundle_structure(bundle, requirement)
    if not structurally_valid.test_cases:
        return structurally_valid
    return validate_bundle_against_plan(structurally_valid, plan)


def validate_bundles_against_source_and_plan(
    bundles: dict[str, TestCaseBundle],
    requirements: list[RequirementForTestCase],
    plans: dict[str, PlannerOutput],
) -> dict[str, TestCaseBundle]:
    """
    Validate all generated bundles.
    Missing bundle or missing plan returns FAILED_SCHEMA_VALIDATION bundle.
    """
    validated: dict[str, TestCaseBundle] = {}

    for requirement in requirements:
        bundle = bundles.get(requirement.id)
        plan = plans.get(requirement.id)

        if bundle is None:
            validated[requirement.id] = make_validation_failed_bundle(
                requirement,
                "Generated bundle missing",
                plan,
            )
            continue

        if plan is None:
            validated[requirement.id] = make_validation_failed_bundle(
                requirement,
                "Planner output missing",
            )
            continue

        validated[requirement.id] = validate_bundle_against_source_and_plan(
            bundle,
            requirement,
            plan,
        )

    return validated
