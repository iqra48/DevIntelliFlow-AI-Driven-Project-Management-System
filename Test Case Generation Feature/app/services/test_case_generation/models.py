from dataclasses import asdict, dataclass, field
from typing import Any, Optional


ALLOWED_REQUIREMENT_TYPES = {"FR", "NFR"}
ALLOWED_MODES = {"mvp_fast", "balanced"}
ALLOWED_STATUSES = {
    "SUCCESS",
    "NEEDS_REVIEW",
    "BLOCKED_MISSING_INFORMATION",
    "FAILED_SCHEMA_VALIDATION",
    "RATE_LIMITED",
    "PROVIDER_FAILED",
}
ALLOWED_REVIEW_DECISIONS = {
    "KEEP",
    "REJECT_UNSUPPORTED_INVENTION",
    "REVIEW_NEEDED",
}
ALLOWED_RISK_LEVELS = {"Low", "Medium", "High"}
ALLOWED_AMBIGUITY_LEVELS = {"Low", "Medium", "High"}
ALLOWED_PRIORITIES = {"High", "Medium", "Low"}
ALLOWED_TEST_TYPES = {
    "Positive",
    "Negative",
    "Boundary",
    "Performance",
    "Security",
    "Reliability",
    "Usability",
    "Compatibility",
    "Recovery",
}


MODE_CONFIG = {
    "mvp_fast": {
        "max_requirements": 3,
        "chunk_size": 3,
        "max_test_cases_per_requirement": 5,
        "max_calls_per_chunk": 4,
    },
    "balanced": {
        "max_requirements": 3,
        "chunk_size": 3,
        "max_test_cases_per_requirement": 5,
        "max_calls_per_chunk": 4,
    },
}


@dataclass
class RequirementForTestCase:
    id: str
    requirement: str
    classification_type: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RequirementForTestCase":
        return cls(**data)


@dataclass
class CoverageItem:
    coverage_item: str
    test_type: str
    technique_used: str
    priority: str
    rationale: str
    source_basis: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoverageItem":
        payload = dict(data)
        payload.setdefault("source_basis", [])
        return cls(**payload)


@dataclass
class PlannerOutput:
    requirement_id: str
    requirement_text: str
    requirement_type: str
    testable: bool
    safe_to_generate: bool
    risk_level: str
    ambiguity_level: str
    blocking_missing_information: list[str]
    missing_information: list[str]
    coverage_items: list[CoverageItem]
    recommended_test_case_count: int
    assumptions: list[str]
    why_negative_not_generated: Optional[str] = None
    why_boundary_not_generated: Optional[str] = None
    coverage_replan_attempted: bool = False
    coverage_replan_reason: Optional[str] = None
    coverage_replan_succeeded: Optional[bool] = None
    planner_parse_attempts: int = 0
    planner_raw_response_excerpt: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlannerOutput":
        payload = dict(data)
        payload.setdefault("why_negative_not_generated", None)
        payload.setdefault("why_boundary_not_generated", None)
        payload["coverage_items"] = [
            item if isinstance(item, CoverageItem) else CoverageItem.from_dict(item)
            for item in payload.get("coverage_items", [])
        ]
        return cls(**payload)


@dataclass
class TestStep:
    step_number: int
    action: str
    expected_result: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestStep":
        return cls(**data)


@dataclass
class TestCase:
    test_case_id: str
    requirement_id: str
    title: str
    objective: str
    test_type: str
    technique_used: str
    priority: str
    preconditions: list[str]
    test_data: dict[str, Any]
    steps: list[TestStep]
    expected_result: str
    assumption_required: bool
    assumptions: list[str]
    traceability: dict[str, str]
    source_basis: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestCase":
        payload = dict(data)
        payload.setdefault("source_basis", [])
        payload["steps"] = [
            step if isinstance(step, TestStep) else TestStep.from_dict(step)
            for step in payload.get("steps", [])
        ]
        return cls(**payload)


@dataclass
class TestCaseBundle:
    requirement_id: str
    requirement_text: str
    requirement_type: str
    status: str
    test_cases: list[TestCase]
    missing_information: list[str]
    assumptions: list[str]
    warnings: list[str]
    reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestCaseBundle":
        payload = dict(data)
        payload["test_cases"] = [
            case if isinstance(case, TestCase) else TestCase.from_dict(case)
            for case in payload.get("test_cases", [])
        ]
        return cls(**payload)


@dataclass
class GenerationBudget:
    mode: str
    estimated_calls: int
    estimated_tokens: int
    calls_used: int = 0
    primary_provider: Optional[str] = None
    strict_provider: Optional[bool] = None
    provider_used_by_stage: dict[str, str] = field(default_factory=dict)
    provider_role_map: dict[str, str] = field(default_factory=dict)
    fallback_used: bool = False
    fallback_provider: Optional[str] = None
    fallback_reason: Optional[str] = None
    rate_limit_stage: Optional[str] = None
    rate_limit_type: Optional[str] = None
    retry_attempts: int = 0
    provider_wait_seconds_total: float = 0.0
    provider_wait_by_stage: dict[str, float] = field(default_factory=dict)
    provider_wait_by_provider: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GenerationBudget":
        return cls(**data)


@dataclass
class TestCaseGenerationResult:
    status: str
    results: list[TestCaseBundle]
    plans: list[PlannerOutput]
    warnings: list[str]
    budget: GenerationBudget

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestCaseGenerationResult":
        payload = dict(data)
        payload["results"] = [
            bundle if isinstance(bundle, TestCaseBundle) else TestCaseBundle.from_dict(bundle)
            for bundle in payload.get("results", [])
        ]
        payload["plans"] = [
            plan if isinstance(plan, PlannerOutput) else PlannerOutput.from_dict(plan)
            for plan in payload.get("plans", [])
        ]
        if not isinstance(payload.get("budget"), GenerationBudget):
            payload["budget"] = GenerationBudget.from_dict(payload["budget"])
        return cls(**payload)


@dataclass
class TestCaseReviewDecision:
    requirement_id: str
    test_case_id: str
    decision: str
    reason: str
    unsupported_elements: list[str]
    required_human_review: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestCaseReviewDecision":
        return cls(**data)


@dataclass
class RequirementReviewResult:
    requirement_id: str
    decisions: list[TestCaseReviewDecision]
    warnings: list[str]
    structural_valid: bool = True
    structural_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RequirementReviewResult":
        payload = dict(data)
        payload.setdefault("structural_valid", True)
        payload.setdefault("structural_errors", [])
        payload["decisions"] = [
            item
            if isinstance(item, TestCaseReviewDecision)
            else TestCaseReviewDecision.from_dict(item)
            for item in payload.get("decisions", [])
        ]
        return cls(**payload)
