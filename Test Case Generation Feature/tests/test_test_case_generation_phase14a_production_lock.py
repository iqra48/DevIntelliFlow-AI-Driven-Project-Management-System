from pathlib import Path

from app.services.test_case_generation.models import ALLOWED_STATUSES
from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
)
from ui.test_case_ui_helpers import (
    PUBLIC_TEST_CASE_STATUSES,
    provider_metadata_display_rows,
    provider_signature_from_budget,
    status_notice_kind,
)


def test_prompt_versions_locked():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_no_approved_status_exists():
    assert "APPROVED" not in ALLOWED_STATUSES
    assert "APPROVED" not in Path("app/services/test_case_generation/models.py").read_text(
        encoding="utf-8"
    )


def test_no_repairer_py_exists():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_allowed_statuses_remain_unchanged():
    assert ALLOWED_STATUSES == {
        "SUCCESS",
        "NEEDS_REVIEW",
        "BLOCKED_MISSING_INFORMATION",
        "FAILED_SCHEMA_VALIDATION",
        "RATE_LIMITED",
        "PROVIDER_FAILED",
    }
    assert PUBLIC_TEST_CASE_STATUSES == ALLOWED_STATUSES


def test_ui_labels_do_not_contain_misleading_approval_text():
    text = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "ui/streamlit_app.py",
            "ui/test_case_ui_helpers.py",
        ]
    )

    assert "Approved" not in text
    assert "Accepted Review" not in text


def test_provider_signature_from_budget_prefers_used_stage_metadata():
    budget = {
        "primary_provider": "groq",
        "provider_role_map": {
            "planner": "cerebras",
            "generator": "groq",
            "reviewer": "cerebras",
        },
        "provider_used_by_stage": {
            "planner": "cerebras",
            "generator": "groq",
            "reviewer": "cerebras",
        },
    }

    assert (
        provider_signature_from_budget(budget)
        == "planner=cerebras|generator=groq|reviewer=cerebras"
    )


def test_provider_metadata_display_rows_are_safe_and_truthful():
    rows = provider_metadata_display_rows(
        {
            "primary_provider": "groq",
            "provider_role_map": {
                "planner": "cerebras",
                "generator": "groq",
                "reviewer": "cerebras",
            },
            "fallback_used": False,
            "provider_wait_seconds_total": 45.125,
        }
    )

    values = {row["label"]: row["value"] for row in rows}
    assert values["Provider strategy"] == (
        "planner=cerebras|generator=groq|reviewer=cerebras"
    )
    assert values["Fallback used"] == "no"
    assert values["Provider wait seconds"] == "45.12"


def test_status_notice_kind_maps_public_statuses():
    assert status_notice_kind("SUCCESS") == "success"
    assert status_notice_kind("NEEDS_REVIEW") == "warning"
    assert status_notice_kind("BLOCKED_MISSING_INFORMATION") == "info"
    assert status_notice_kind("RATE_LIMITED") == "error"
    assert status_notice_kind("PROVIDER_FAILED") == "error"
    assert status_notice_kind("FAILED_SCHEMA_VALIDATION") == "error"


def test_documentation_contains_hybrid_provider_strategy():
    text = Path("docs/provider_strategy.md").read_text(encoding="utf-8")

    assert "Planner: Cerebras `gpt-oss-120b`" in text
    assert "Generator: Groq `llama-3.1-8b-instant`" in text
    assert "Reviewer: Cerebras `gpt-oss-120b`" in text
    assert "planner=cerebras|generator=groq|reviewer=cerebras" in text
    assert "CEREBRAS_MIN_SECONDS_BETWEEN_CALLS=45" in text
    assert "LLM_CALL_TIMEOUT_SECONDS=120" in text


def test_documentation_contains_evaluation_baseline():
    text = Path("docs/evaluation_baseline.md").read_text(encoding="utf-8")

    assert "total_eval_items=45" in text
    assert "schema_pass_rate=1.0" in text
    assert "unsupported_invention_rate=0.022222222222222223" in text
    assert "rate_limit_failures=0" in text
    assert "provider_failures=0" in text
    assert "phase12_gate_passed=true" in text


def test_documentation_contains_honest_human_review_limitation():
    combined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "docs/test_case_generation.md",
            "docs/evaluation_baseline.md",
        ]
    )

    assert "AI-assisted QA drafts" in combined
    assert "human QA review is still expected" in combined
    assert "fully automatic final approval" in combined


def test_streamlit_displays_subtle_review_note_and_opt_in_diagnostics():
    text = Path("ui/streamlit_app.py").read_text(encoding="utf-8")

    assert "Generated test cases are AI-assisted QA drafts" not in text
    assert "Review generated test cases before execution." in text
    assert "Show technical details" in text
    assert "if show_technical_details:" in text
    assert "Provider Metadata" in text
    assert "Fallback used" in Path("ui/test_case_ui_helpers.py").read_text(
        encoding="utf-8"
    )
    assert "Test case count" in text
    assert "Clarification is needed" in text
    assert "Provider error occurred" in text


def test_no_semantic_keyword_logic_added():
    combined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "ui/streamlit_app.py",
            "ui/test_case_ui_helpers.py",
            "app/shared/llm/call_llm.py",
            "app/shared/llm/llm_router.py",
        ]
    )

    assert "requirement" + ".lower(" not in combined
    assert 'if "' + "login" + '" in' not in combined
    assert 'if "' + "button" + '" in' not in combined
    assert 'if "' + "password" + '" in' not in combined
    assert "similarity" not in combined
    assert "fuzzy" not in combined


