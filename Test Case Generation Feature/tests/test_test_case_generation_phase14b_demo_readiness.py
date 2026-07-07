from pathlib import Path

from app.services.test_case_generation.prompts import (
    TEST_CASE_GENERATOR_PROMPT_VERSION,
    TEST_CASE_PROMPT_VERSION,
    TEST_CASE_REVIEWER_PROMPT_VERSION,
)


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_env_example_exists():
    assert Path(".env.example").exists()


def test_env_example_contains_locked_stage_routing_profile():
    text = read(".env.example")

    for line in [
        "LLM_PROVIDER=groq",
        "LLM_STRICT_PROVIDER=false",
        "LLM_PROVIDER_ROUTING_MODE=stage",
        "LLM_PLANNER_PROVIDER=cerebras",
        "LLM_GENERATOR_PROVIDER=groq",
        "LLM_REVIEWER_PROVIDER=cerebras",
        "LLM_FALLBACK_POLICY=rate_limit_only",
        "LLM_ALLOWED_FALLBACKS=cerebras",
        "CEREBRAS_MODEL=gpt-oss-120b",
        "TEST_CASE_CACHE_ENABLED=true",
    ]:
        assert line in text


def test_env_example_contains_no_real_looking_api_key_values():
    text = read(".env.example")

    assert "GROQ_API_KEY=your_groq_key_here" in text
    assert "CEREBRAS_API_KEY=your_cerebras_key_here" in text
    assert "gsk_" not in text
    assert "csk-" not in text


def test_env_example_contains_cerebras_pacing_and_timeout():
    text = read(".env.example")

    assert "CEREBRAS_MIN_SECONDS_BETWEEN_CALLS=45" in text
    assert "LLM_CALL_TIMEOUT_SECONDS=120" in text


def test_gitignore_contains_env_secret_ignore():
    assert ".env" in read(".gitignore").splitlines()


def test_gitignore_contains_pycache_log_and_temp_ignores():
    lines = set(read(".gitignore").splitlines())

    for item in [
        ".env.local",
        "*.log",
        "__pycache__/",
        "*.pyc",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        "tmp_uvicorn_pid.txt",
        "server_err.log",
        "server_out.log",
    ]:
        assert item in lines


def test_demo_runbook_contains_backend_start_command():
    assert (
        "python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
        in read("docs/demo_runbook.md")
    )


def test_demo_runbook_contains_streamlit_start_command():
    assert "streamlit run ui/streamlit_app.py" in read("docs/demo_runbook.md")


def test_demo_runbook_contains_groq_health_check():
    assert "/health/groq" in read("docs/demo_runbook.md")


def test_demo_runbook_contains_cerebras_health_check():
    assert "/health/cerebras" in read("docs/demo_runbook.md")


def test_demo_runbook_contains_sample_generate_test_cases_payload():
    text = read("docs/demo_runbook.md")

    assert "/generate_test_cases" in text
    assert '"requirement": "User can log in to the system."' in text
    assert '"classification_type": "FR"' in text
    assert '"mode": "mvp_fast"' in text


def test_demo_docs_mention_ai_assisted_qa_drafts():
    combined = read("docs/demo_runbook.md") + read("docs/test_case_generation.md")

    assert "AI-assisted QA drafts" in combined


def test_demo_docs_mention_human_review_before_execution():
    combined = read("docs/demo_runbook.md") + read("docs/test_case_generation.md")

    assert "Human QA review is expected before execution" in combined


def test_provider_docs_still_contain_locked_signature():
    assert (
        "planner=cerebras|generator=groq|reviewer=cerebras"
        in read("docs/provider_strategy.md")
    )


def test_evaluation_baseline_still_contains_phase_gate_passed():
    assert "phase12_gate_passed=true" in read("docs/evaluation_baseline.md")


def test_no_approved_status_added():
    assert "APPROVED" not in read("app/services/test_case_generation/models.py")


def test_no_repairer_py_exists():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_prompt_versions_unchanged():
    assert TEST_CASE_PROMPT_VERSION == "planner_v13"
    assert TEST_CASE_GENERATOR_PROMPT_VERSION == "generator_v8"
    assert TEST_CASE_REVIEWER_PROMPT_VERSION == "reviewer_v6"


def test_no_provider_selector_ui_added():
    text = read("ui/streamlit_app.py").casefold()

    assert "provider selector" not in text
    assert "select provider" not in text
    assert "llm provider" not in text


