import asyncio
import sys
from pathlib import Path

import pytest

import scripts.run_test_case_evaluation as eval_script
from app.services.test_case_generation.cache import clear_test_case_cache
from app.services.test_case_generation.errors import rate_limit_type_from_exception
from app.services.test_case_generation.models import RequirementForTestCase
from app.services.test_case_generation.orchestrator import TestCaseEngine
from app.shared.llm import call_llm as call_llm_module
from app.shared.llm import llm_router
from app.shared.llm.exceptions import StrictProviderFallbackBlocked
from app.shared.llm.provider_metadata import request_provider_metadata_ctx
from app.shared.llm.provider_governor import parse_retry_after_seconds


class RateLimit429(Exception):
    status_code = 429


class FakeGroqProvider:
    calls = 0
    responses = []

    def __init__(self):
        pass

    async def generate(self, **kwargs):
        type(self).calls += 1
        if type(self).responses:
            response = type(self).responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return "{}"


class FakeOllamaProvider:
    calls = 0

    def __init__(self):
        pass

    async def generate(self, **kwargs):
        type(self).calls += 1
        return "{}"


class FakeOpenRouterProvider(FakeOllamaProvider):
    pass


@pytest.fixture(autouse=True)
def reset_fakes(monkeypatch):
    clear_test_case_cache()
    monkeypatch.delenv("LLM_PROVIDER_ROUTING_MODE", raising=False)
    monkeypatch.delenv("LLM_PLANNER_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_GENERATOR_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_REVIEWER_PROVIDER", raising=False)
    FakeGroqProvider.calls = 0
    FakeGroqProvider.responses = []
    FakeOllamaProvider.calls = 0
    FakeOpenRouterProvider.calls = 0
    monkeypatch.setattr(llm_router, "GroqProvider", FakeGroqProvider)
    monkeypatch.setattr(llm_router, "OllamaProvider", FakeOllamaProvider)
    monkeypatch.setattr(llm_router, "OpenRouterProvider", FakeOpenRouterProvider)
    monkeypatch.setattr(call_llm_module, "_router", None)
    yield
    clear_test_case_cache()


def make_router(monkeypatch, provider="groq", strict="true", policy="none", allowed=""):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("LLM_STRICT_PROVIDER", strict)
    monkeypatch.setenv("LLM_PROVIDER_ROUTING_MODE", "default")
    monkeypatch.setenv("LLM_FALLBACK_POLICY", policy)
    monkeypatch.setenv("LLM_ALLOWED_FALLBACKS", allowed)
    monkeypatch.setenv("GROQ_API_KEY", "test")
    return llm_router.LLMRouter()


def test_strict_groq_mode_still_attempts_only_groq(monkeypatch):
    router = make_router(monkeypatch, strict="true", allowed="ollama")

    assert [type(provider).__name__ for provider in router.providers] == ["FakeGroqProvider"]


def test_strict_groq_mode_does_not_fallback_after_groq_429(monkeypatch):
    router = make_router(monkeypatch, strict="true", policy="rate_limit_only", allowed="ollama")
    FakeGroqProvider.responses = [RateLimit429("Rate limit reached on tokens per minute")]

    with pytest.raises(StrictProviderFallbackBlocked):
        asyncio.run(router.generate("prompt", stage="planner"))

    assert FakeGroqProvider.calls == 1
    assert FakeOllamaProvider.calls == 0


def test_non_strict_policy_none_does_not_fallback(monkeypatch):
    router = make_router(monkeypatch, strict="false", policy="none", allowed="ollama")
    FakeGroqProvider.responses = [RateLimit429("Rate limit reached")]

    with pytest.raises(RateLimit429):
        asyncio.run(router.generate("prompt", stage="planner"))

    assert FakeOllamaProvider.calls == 0


def test_non_strict_fallback_policy_empty_allowed_list_does_not_fallback(monkeypatch):
    router = make_router(monkeypatch, strict="false", policy="rate_limit_only", allowed="")
    FakeGroqProvider.responses = [RateLimit429("Rate limit reached")]

    with pytest.raises(RateLimit429):
        asyncio.run(router.generate("prompt", stage="planner"))

    assert FakeOllamaProvider.calls == 0


def test_non_strict_does_not_fallback_to_ollama_unless_explicitly_allowed(monkeypatch):
    router = make_router(monkeypatch, strict="false", policy="rate_limit_only", allowed="openrouter")

    assert [type(provider).__name__ for provider in router.providers] == [
        "FakeGroqProvider",
        "FakeOpenRouterProvider",
    ]


def test_non_strict_does_not_fallback_to_openrouter_unless_explicitly_allowed(monkeypatch):
    router = make_router(monkeypatch, strict="false", policy="rate_limit_only", allowed="ollama")

    assert [type(provider).__name__ for provider in router.providers] == [
        "FakeGroqProvider",
        "FakeOllamaProvider",
    ]


def test_allowed_fallback_list_parses_casefold_and_whitespace(monkeypatch):
    monkeypatch.setenv("LLM_ALLOWED_FALLBACKS", " OLLAMA, openrouter , OLLAMA ")

    assert llm_router.allowed_fallbacks() == ["ollama", "openrouter"]


def test_provider_metadata_is_present_in_generation_response(monkeypatch):
    async def fake_generate(prompt, system_prompt=None, model=None, num_predict=None, stage=None):
        metadata = request_provider_metadata_ctx.get()
        metadata["provider_used_by_stage"][stage] = "groq"
        return '{"plans": {"1": {"requirement_id":"REQ_1","requirement_text":"The system shall process item REQ_1.","requirement_type":"FR","testable":false,"safe_to_generate":false,"risk_level":"Low","ambiguity_level":"High","blocking_missing_information":["Missing detail"],"missing_information":[],"coverage_items":[],"recommended_test_case_count":0,"assumptions":[]}}}'

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "true")
    monkeypatch.setattr("app.services.test_case_generation.planner.call_llm", fake_generate)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))
    budget = result.budget.to_dict()

    assert "primary_provider" in budget
    assert "strict_provider" in budget
    assert "provider_used_by_stage" in budget


def test_provider_metadata_records_primary_provider_groq(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "true")

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()], mode="mvp_fast"))

    assert result.budget.primary_provider == "groq"


def test_provider_metadata_records_strict_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "false")

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()], mode="mvp_fast"))

    assert result.budget.strict_provider is False


def test_provider_metadata_records_fallback_false_in_strict_groq(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "true")

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()], mode="mvp_fast"))

    assert result.budget.fallback_used is False


def test_provider_metadata_records_rate_limit_stage(monkeypatch):
    async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
        metadata = request_provider_metadata_ctx.get()
        metadata["rate_limit_stage"] = "planner"
        metadata["rate_limit_type"] = "TPM"
        raise RateLimit429("Rate limit reached on tokens per minute")

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "true")
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.budget.rate_limit_stage == "planner"
    assert result.budget.rate_limit_type == "TPM"


def test_groq_tpm_tpd_detection_works_from_error_text():
    assert rate_limit_type_from_exception(
        RateLimit429("Rate limit reached on tokens per minute")
    ) == "TPM"
    assert rate_limit_type_from_exception(
        RateLimit429("Rate limit reached on tokens per day")
    ) == "TPD"


def test_retry_after_parser_handles_minutes_and_seconds():
    assert parse_retry_after_seconds("Please try again in 1m2.5s") == 62.5
    assert parse_retry_after_seconds("Please try again in 1.1s") == 1.1


def test_no_retry_when_max_retry_after_seconds_zero(monkeypatch):
    router = make_router(monkeypatch, strict="false", policy="none")
    monkeypatch.setenv("LLM_MAX_RETRY_AFTER_SECONDS", "0")
    FakeGroqProvider.responses = [
        RateLimit429("Rate limit reached. Please try again in 1.1s")
    ]

    with pytest.raises(RateLimit429):
        asyncio.run(router.generate("prompt", stage="planner"))

    assert FakeGroqProvider.calls == 1


def test_one_retry_happens_when_retry_after_is_within_allowed_max(monkeypatch):
    router = make_router(monkeypatch, strict="false", policy="none")
    monkeypatch.setenv("LLM_MAX_RETRY_AFTER_SECONDS", "2")
    monkeypatch.setattr(llm_router.asyncio, "sleep", _no_sleep)
    FakeGroqProvider.responses = [
        RateLimit429("Rate limit reached. Please try again in 1.1s"),
        "ok",
    ]

    assert asyncio.run(router.generate("prompt", stage="planner")) == "ok"
    assert FakeGroqProvider.calls == 2


def test_no_infinite_retry(monkeypatch):
    router = make_router(monkeypatch, strict="false", policy="none")
    monkeypatch.setenv("LLM_MAX_RETRY_AFTER_SECONDS", "2")
    monkeypatch.setattr(llm_router.asyncio, "sleep", _no_sleep)
    FakeGroqProvider.responses = [
        RateLimit429("Rate limit reached. Please try again in 1.1s"),
        RateLimit429("Rate limit reached. Please try again in 1.1s"),
    ]

    with pytest.raises(RateLimit429):
        asyncio.run(router.generate("prompt", stage="planner"))

    assert FakeGroqProvider.calls == 2


def test_run_test_case_evaluation_supports_sleep_between_items(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_test_case_evaluation.py",
            "--dry-run",
            "--limit",
            "0",
            "--reports-dir",
            str(tmp_path),
            "--sleep-between-items",
            "70",
        ],
    )

    assert eval_script.main() == 0
    assert "sleep_between_items=70.0" in capsys.readouterr().out


def test_require_groq_only_still_enforces_strict_groq(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "false")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_test_case_evaluation.py",
            "--live",
            "--limit",
            "0",
            "--reports-dir",
            str(tmp_path),
            "--require-groq-only",
        ],
    )

    assert eval_script.main() == 2


def test_strict_groq_eval_does_not_use_fallback_even_if_allowed(monkeypatch):
    router = make_router(monkeypatch, strict="true", policy="any_failure", allowed="ollama")

    assert [type(provider).__name__ for provider in router.providers] == ["FakeGroqProvider"]


def test_no_approved_status_added():
    text = Path("app/services/test_case_generation/models.py").read_text(encoding="utf-8")

    assert "APPROVED" not in text


def test_no_repairer_py_added():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_no_provider_adapter_added():
    assert not Path("app/shared/llm/gemini_provider.py").exists()
    assert not Path("app/shared/llm/openai_provider.py").exists()
    assert not Path("app/shared/llm/fireworks_provider.py").exists()
    assert not Path("app/shared/llm/litellm_provider.py").exists()


def test_no_python_semantic_keyword_logic():
    combined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "app/shared/llm/llm_router.py",
            "app/shared/llm/call_llm.py",
            "app/services/test_case_generation/orchestrator.py",
        ]
    )

    assert "requirement" + ".lower(" not in combined
    assert 'if "' + "login" + '" in' not in combined
    assert "fuzzy" not in combined
    assert "similarity" not in combined
    assert "contains(" not in combined
    assert "startswith(" not in combined


def raw_requirement():
    return {
        "id": "REQ_1",
        "requirement": "The system shall process item REQ_1.",
        "classification_type": "FR",
    }


async def _no_sleep(seconds):
    return None
