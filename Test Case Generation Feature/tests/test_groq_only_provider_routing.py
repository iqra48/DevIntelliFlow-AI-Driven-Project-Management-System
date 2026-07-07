import asyncio
from pathlib import Path

import pytest

import app.shared.llm.call_llm as call_llm_module
import app.shared.llm.llm_router as router_module
from app.services.test_case_generation.errors import provider_status_from_exception
from app.shared.llm.llm_router import (
    GroqGovernorLimitExceeded,
    LLMRouter,
    StrictProviderFallbackBlocked,
)
from app.shared.llm.provider_governor import ProviderGovernor


class FakeGroqProvider:
    calls = 0
    fail = None

    async def generate(self, **kwargs):
        self.__class__.calls += 1
        if self.__class__.fail is not None:
            raise self.__class__.fail
        return "GROQ_OK"


class FakeOpenRouterProvider:
    calls = 0

    async def generate(self, **kwargs):
        self.__class__.calls += 1
        return "OPENROUTER_OK"


class FakeOllamaProvider:
    calls = 0

    async def generate(self, **kwargs):
        self.__class__.calls += 1
        return "OLLAMA_OK"


@pytest.fixture(autouse=True)
def reset_router_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "true")
    monkeypatch.setenv("GROQ_DAILY_TOKEN_LIMIT", "100000")
    monkeypatch.setattr(router_module, "GroqProvider", FakeGroqProvider)
    monkeypatch.setattr(router_module, "OpenRouterProvider", FakeOpenRouterProvider)
    monkeypatch.setattr(router_module, "OllamaProvider", FakeOllamaProvider)
    FakeGroqProvider.calls = 0
    FakeGroqProvider.fail = None
    FakeOpenRouterProvider.calls = 0
    FakeOllamaProvider.calls = 0
    yield


def test_strict_groq_mode_uses_only_groq_provider():
    router = LLMRouter()

    assert [provider.__class__ for provider in router.providers] == [FakeGroqProvider]


def test_strict_groq_mode_does_not_try_openrouter_after_governor_denial(monkeypatch):
    monkeypatch.setenv("GROQ_DAILY_TOKEN_LIMIT", "1")
    router = LLMRouter()

    with pytest.raises(GroqGovernorLimitExceeded):
        asyncio.run(router.generate(prompt="hello", num_predict=10))

    assert FakeGroqProvider.calls == 0
    assert FakeOpenRouterProvider.calls == 0


def test_strict_groq_mode_does_not_try_ollama_after_governor_denial(monkeypatch):
    monkeypatch.setenv("GROQ_DAILY_TOKEN_LIMIT", "1")
    router = LLMRouter()

    with pytest.raises(GroqGovernorLimitExceeded):
        asyncio.run(router.generate(prompt="hello", num_predict=10))

    assert FakeOllamaProvider.calls == 0


def test_strict_groq_mode_does_not_try_fallback_after_groq_exception():
    FakeGroqProvider.fail = RuntimeError("network failed")
    router = LLMRouter()

    with pytest.raises(StrictProviderFallbackBlocked):
        asyncio.run(router.generate(prompt="hello", num_predict=10))

    assert FakeGroqProvider.calls == 1
    assert FakeOpenRouterProvider.calls == 0
    assert FakeOllamaProvider.calls == 0


def test_non_strict_mode_without_fallback_policy_does_not_fallback(monkeypatch):
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "false")
    FakeGroqProvider.fail = RuntimeError("network failed")
    router = LLMRouter()

    with pytest.raises(RuntimeError):
        asyncio.run(router.generate(prompt="hello", num_predict=10))

    assert FakeOpenRouterProvider.calls == 0


def test_non_strict_mode_uses_explicit_allowed_fallback(monkeypatch):
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "false")
    monkeypatch.setenv("LLM_FALLBACK_POLICY", "any_failure")
    monkeypatch.setenv("LLM_ALLOWED_FALLBACKS", "openrouter")
    FakeGroqProvider.fail = RuntimeError("network failed")
    router = LLMRouter()

    result = asyncio.run(router.generate(prompt="hello", num_predict=10))

    assert result == "OPENROUTER_OK"
    assert FakeOpenRouterProvider.calls == 1


def test_local_governor_denial_raises_clear_exception(monkeypatch):
    monkeypatch.setenv("GROQ_DAILY_TOKEN_LIMIT", "1")
    router = LLMRouter()

    with pytest.raises(GroqGovernorLimitExceeded) as exc_info:
        asyncio.run(router.generate(prompt="hello", num_predict=10))

    message = str(exc_info.value)
    assert "estimated_tokens=" in message
    assert "daily_limit=1" in message


def test_groq_governor_limit_exceeded_is_rate_limited():
    exc = GroqGovernorLimitExceeded("local cap")

    assert provider_status_from_exception(exc) == "RATE_LIMITED"


def test_can_use_groq_does_not_mutate_tokens_used():
    governor = ProviderGovernor()
    before = governor.tokens_used

    allowed, reason = governor.can_use_groq(10)

    assert allowed is True
    assert reason is None
    assert governor.tokens_used == before


def test_failed_groq_attempt_does_not_increment_tokens_used():
    governor = ProviderGovernor()

    governor.record_groq_failure(RuntimeError("temporary network failure"))

    assert governor.tokens_used == 0


def test_successful_groq_attempt_records_usage_once():
    governor = ProviderGovernor()

    governor.record_groq_usage(25)

    assert governor.tokens_used == 25


def test_governor_denies_when_estimated_usage_would_exceed_cap(monkeypatch):
    monkeypatch.setenv("GROQ_DAILY_TOKEN_LIMIT", "100")
    governor = ProviderGovernor()
    governor.record_groq_usage(90)

    allowed, reason = governor.can_use_groq(10)

    assert allowed is False
    assert "daily_limit=100" in reason


def test_default_cap_remains_configurable_by_env(monkeypatch):
    monkeypatch.setenv("GROQ_DAILY_TOKEN_LIMIT", "12345")

    assert ProviderGovernor().daily_limit == 12345


def test_call_llm_strict_mode_does_not_use_ollama_fallback(monkeypatch):
    async def fail_router_generate(**kwargs):
        raise GroqGovernorLimitExceeded("local cap")

    class FailIfConstructed:
        def __init__(self):
            raise AssertionError("Ollama fallback must not be constructed")

    class FakeRouter:
        async def generate(self, **kwargs):
            return await fail_router_generate(**kwargs)

    monkeypatch.setattr(call_llm_module, "_router", FakeRouter())

    with pytest.raises(GroqGovernorLimitExceeded):
        asyncio.run(call_llm_module.call_llm("prompt", num_predict=1))


def test_touched_provider_files_have_no_lower_usage():
    combined = "\n".join(
        Path(path).read_text()
        for path in [
            "app/shared/llm/llm_router.py",
            "app/shared/llm/provider_governor.py",
            "app/shared/llm/call_llm.py",
        ]
    )

    assert ".lower(" not in combined
