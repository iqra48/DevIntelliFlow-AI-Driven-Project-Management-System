from pathlib import Path

from app.services.test_case_generation.models import RequirementReviewResult
from app.services.test_case_generation.orchestrator import apply_review_results
from app.services.test_case_generation.reviewer import parse_reviewer_response
from tests.test_test_case_generation_phase13a_reviewer_filter import decision_payload
from tests.test_test_case_generation_phase6_orchestrator import (
    bundle_for,
    case_for,
    requirement_from_raw,
    raw_requirement,
)


IMPLEMENTATION_FILES = [
    Path("app/services/test_case_generation/cache.py"),
    Path("app/services/test_case_generation/orchestrator.py"),
    Path("app/services/test_case_generation/reviewer.py"),
]


def requirement(requirement_id="REQ_1"):
    return requirement_from_raw(raw_requirement(requirement_id))


def parsed_review(raw_decisions, req=None, bundle=None):
    req = req or requirement()
    bundle = bundle or bundle_for(req, [case_for(req)])
    raw = {
        "reviews": {
            "1": {
                "requirement_id": req.id,
                "decisions": raw_decisions,
                "warnings": [],
            }
        }
    }
    return parse_reviewer_response(raw, [req], {req.id: bundle})[req.id]


def applied(decision, req=None, bundle=None):
    req = req or requirement()
    bundle = bundle or bundle_for(req, [case_for(req)])
    review = parsed_review([decision], req, bundle)
    return apply_review_results({req.id: bundle}, {req.id: review})[req.id]


def test_unknown_reviewer_test_case_id_marks_review_structurally_invalid():
    review = parsed_review([decision_payload("TC_UNKNOWN", "KEEP")])

    assert review.structural_valid is False
    assert any("Unknown reviewer test_case_id" in item for item in review.structural_errors)


def test_invalid_reviewer_decision_enum_marks_review_structurally_invalid():
    req = requirement()
    case = case_for(req)
    review = parsed_review([decision_payload(case.test_case_id, "NOT_VALID")], req)

    assert review.structural_valid is False
    assert any("Invalid reviewer decision" in item for item in review.structural_errors)


def test_structurally_invalid_review_returns_needs_review():
    result = applied(decision_payload("TC_UNKNOWN", "KEEP"))

    assert result.status == "NEEDS_REVIEW"


def test_structurally_invalid_review_withholds_test_cases():
    result = applied(decision_payload("TC_UNKNOWN", "KEEP"))

    assert result.test_cases == []


def test_structurally_invalid_warning_is_present():
    result = applied(decision_payload("TC_UNKNOWN", "KEEP"))

    assert "Reviewer output structurally invalid; generated cases withheld for human review" in result.warnings


def test_structurally_invalid_reason_is_set():
    result = applied(decision_payload("TC_UNKNOWN", "KEEP"))

    assert result.reason == "Reviewer output structurally invalid"


def test_valid_keep_still_keeps_case():
    req = requirement()
    case = case_for(req)
    result = applied(decision_payload(case.test_case_id, "KEEP"), req)

    assert result.status == "SUCCESS"
    assert result.test_cases == [case]


def test_valid_review_needed_keeps_case_and_marks_needs_review():
    req = requirement()
    case = case_for(req)
    result = applied(decision_payload(case.test_case_id, "REVIEW_NEEDED"), req)

    assert result.status == "NEEDS_REVIEW"
    assert result.test_cases == [case]


def test_valid_reject_unsupported_invention_removes_case():
    req = requirement()
    case = case_for(req)
    result = applied(decision_payload(case.test_case_id, "REJECT_UNSUPPORTED_INVENTION"), req)

    assert result.test_cases == []


def test_all_rejected_returns_needs_review_with_empty_test_cases():
    req = requirement()
    case = case_for(req)
    result = applied(decision_payload(case.test_case_id, "REJECT_UNSUPPORTED_INVENTION"), req)

    assert result.status == "NEEDS_REVIEW"
    assert result.test_cases == []


def test_missing_reviewer_decision_for_known_case_does_not_produce_success():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])
    review = parsed_review([], req, bundle)
    result = apply_review_results({req.id: bundle}, {req.id: review})[req.id]

    assert result.status == "NEEDS_REVIEW"


def test_malformed_reviewer_top_level_response_marks_review_needed_safely():
    req = requirement()
    bundle = bundle_for(req, [case_for(req)])
    review = parse_reviewer_response("not json", [req], {req.id: bundle})[req.id]
    result = apply_review_results({req.id: bundle}, {req.id: review})[req.id]

    assert result.status == "NEEDS_REVIEW"
    assert result.test_cases == bundle.test_cases


def test_no_approved_status_added():
    text = Path("app/services/test_case_generation/models.py").read_text(encoding="utf-8")

    assert '"APPROVED"' not in text
    assert "'APPROVED'" not in text


def test_no_repairer_py_added():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_no_provider_or_fallback_changes_in_reviewer_fail_closed_files():
    combined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "app/services/test_case_generation/reviewer.py",
            "app/services/test_case_generation/orchestrator.py",
        ]
    )

    assert "Gemini" not in combined
    assert "Cerebras" not in combined
    assert "fallback provider" not in combined


def test_no_requirement_lower():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES)

    assert "requirement" + ".lower(" not in combined


def test_no_lower_call_added():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES)

    assert ".lower(" not in combined


def test_no_keyword_branches():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES)
    fragments = [
        'if "' + "login" + '" in',
        "if '" + "login" + "' in",
        'if "' + "manager" + '" in',
        "if '" + "manager" + "' in",
        'if "' + "button" + '" in',
        "if '" + "button" + "' in",
        'if "' + "page" + '" in',
        "if '" + "page" + "' in",
    ]

    for fragment in fragments:
        assert fragment not in combined


def test_no_fuzzy_similarity_contains_startswith():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES)

    assert "fuzzy" not in combined
    assert "similarity" not in combined
    assert "contains(" not in combined
    assert "startswith(" not in combined


def test_requirement_review_result_from_dict_defaults_structural_fields():
    result = RequirementReviewResult.from_dict(
        {"requirement_id": "REQ_1", "decisions": [], "warnings": []}
    )

    assert result.structural_valid is True
    assert result.structural_errors == []
