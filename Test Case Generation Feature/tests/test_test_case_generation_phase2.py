from app.services.test_case_generation.models import GenerationBudget, RequirementForTestCase
from app.services.test_case_generation.token_budget import (
    count_words,
    estimate_calls,
    estimate_generation_budget,
    estimate_response,
    estimate_tokens,
    generator_tokens,
    generator_tokens_preplan,
    planner_tokens,
)


def raw_requirement(
    requirement_id="REQ_1",
    requirement="The system shall export reports.",
    classification_type="FR",
):
    return {
        "id": requirement_id,
        "requirement": requirement,
        "classification_type": classification_type,
    }


def requirement(requirement_id="REQ_1", classification_type="FR"):
    return RequirementForTestCase(
        id=requirement_id,
        requirement="The system shall export reports.",
        classification_type=classification_type,
    )


def test_count_words_returns_zero_for_non_string_input():
    assert count_words(None) == 0
    assert count_words(123) == 0


def test_planner_tokens_clamps_to_minimum_for_tiny_input():
    assert planner_tokens([]) == 900


def test_planner_tokens_cap_is_greater_than_old_900_limit():
    requirements = [
        RequirementForTestCase(
            id=f"REQ_{index}",
            requirement="The system shall support a detailed capability with enough words to increase planner output needs.",
            classification_type="FR",
        )
        for index in range(1, 6)
    ]

    assert planner_tokens(requirements) > 900


def test_generator_tokens_preplan_clamps_to_minimum_for_tiny_input():
    assert generator_tokens_preplan([]) == 1200


def test_generator_tokens_supports_five_requirements_with_three_cases_each():
    requirements = [requirement(f"REQ_{index}") for index in range(1, 6)]

    assert generator_tokens(requirements, [3, 3, 3, 3, 3]) > 1800
    assert generator_tokens(requirements, [3, 3, 3, 3, 3]) <= 5600


def test_estimate_calls_returns_four_for_one_mvp_fast_chunk():
    assert estimate_calls([requirement()], mode="mvp_fast") == 4


def test_estimate_calls_returns_four_for_five_mvp_fast_requirements():
    requirements = [requirement(f"REQ_{index}") for index in range(1, 6)]

    assert estimate_calls(requirements, mode="mvp_fast") == 4


def test_estimate_calls_returns_four_for_three_balanced_requirements():
    requirements = [requirement(f"REQ_{index}") for index in range(1, 4)]

    assert estimate_calls(requirements, mode="balanced") == 4


def test_estimate_tokens_returns_positive_integer():
    result = estimate_tokens([requirement()], mode="mvp_fast")

    assert isinstance(result, int)
    assert result > 0


def test_estimate_generation_budget_returns_budget_with_calls_used_zero():
    normalized, budget, warnings = estimate_generation_budget([raw_requirement()])

    assert len(normalized) == 1
    assert isinstance(budget, GenerationBudget)
    assert budget.calls_used == 0
    assert warnings == []


def test_estimate_response_allowed_true_for_valid_request():
    result = estimate_response([raw_requirement()])

    assert result["allowed"] is True
    assert result["mode"] == "mvp_fast"
    assert result["requirement_count"] == 1
    assert result["estimated_calls"] == 4
    assert result["estimated_tokens"] > 0
    assert result["max_requirements"] == 3
    assert result["chunk_size"] == 3
    assert result["warnings"] == []


def test_estimate_response_allowed_false_for_mixed_requirement():
    result = estimate_response([raw_requirement(classification_type="MIXED")])

    assert result["allowed"] is False
    assert result["estimated_calls"] == 0
    assert result["estimated_tokens"] == 0
    assert result["warnings"]


def test_estimate_response_allowed_false_for_too_many_mvp_fast_requirements():
    raw_requirements = [
        raw_requirement(requirement_id=f"REQ_{index}")
        for index in range(1, 5)
    ]

    result = estimate_response(raw_requirements, mode="mvp_fast")

    assert result["allowed"] is False
    assert result["max_requirements"] == 3
    assert result["chunk_size"] == 3
    assert result["warnings"] == ["mode mvp_fast allows at most 3 requirements"]


def test_estimate_response_allowed_false_for_invalid_mode():
    result = estimate_response([raw_requirement()], mode="slow")

    assert result["allowed"] is False
    assert result["max_requirements"] is None
    assert result["chunk_size"] is None
    assert result["warnings"]


def test_estimate_endpoint_valid_request_returns_allowed_true():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/generate_test_cases/estimate",
        json={"requirements": [raw_requirement()], "mode": "mvp_fast"},
    )

    assert response.status_code == 200
    assert response.json()["allowed"] is True


def test_estimate_endpoint_mixed_request_returns_allowed_false():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/generate_test_cases/estimate",
        json={
            "requirements": [raw_requirement(classification_type="MIXED")],
            "mode": "mvp_fast",
        },
    )

    assert response.status_code == 200
    assert response.json()["allowed"] is False


def test_estimate_endpoint_too_many_requirements_returns_allowed_false():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/generate_test_cases/estimate",
        json={
            "requirements": [
                raw_requirement(requirement_id=f"REQ_{index}")
                for index in range(1, 5)
            ],
            "mode": "mvp_fast",
        },
    )

    assert response.status_code == 200
    assert response.json()["allowed"] is False
