import asyncio
from pathlib import Path

import pytest

from app.shared.llm import call_llm as call_llm_module
from app.shared.llm import llm_router
from app.shared.llm.provider_metadata import request_provider_metadata_ctx
from app.services.test_case_generation.evaluation import aggregate_eval_rows
from tests.test_test_case_generation_phase13j_provider_aware_eval import (
    provider_budget,
    row_from_budget,
)


class FakeProviderBase:
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


class FakeGroqProvider(FakeProviderBase):
    pass


class FakeCerebrasProvider(FakeProviderBase):
    pass


class FakeOpenRouterProvider(FakeProviderBase):
    pass


class FakeOllamaProvider(FakeProviderBase):
    pass


class RateLimit429(Exception):
    status_code = 429


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    for provider in [
        FakeGroqProvider,
        FakeCerebrasProvider,
        FakeOpenRouterProvider,
        FakeOllamaProvider,
    ]:
        provider.calls = 0
        provider.responses = []
    monkeypatch.setattr(llm_router, "GroqProvider", FakeGroqProvider)
    monkeypatch.setattr(llm_router, "CerebrasProvider", FakeCerebrasProvider)
    monkeypatch.setattr(llm_router, "OpenRouterProvider", FakeOpenRouterProvider)
    monkeypatch.setattr(llm_router, "OllamaProvider", FakeOllamaProvider)
    monkeypatch.setattr(call_llm_module, "_router", None)
    monkeypatch.delenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", raising=False)
    monkeypatch.delenv("GROQ_MIN_SECONDS_BETWEEN_CALLS", raising=False)
    monkeypatch.delenv("OPENROUTER_MIN_SECONDS_BETWEEN_CALLS", raising=False)
    monkeypatch.delenv("OLLAMA_MIN_SECONDS_BETWEEN_CALLS", raising=False)
    request_provider_metadata_ctx.set(None)


def test_default_provider_pacing_is_zero(monkeypatch):
    clock = FakeClock(monkeypatch)
    router = make_router(monkeypatch, provider="cerebras")

    asyncio.run(call_twice(router, stage="planner"))

    assert clock.sleeps == []


def test_cerebras_first_call_does_not_wait(monkeypatch):
    clock = FakeClock(monkeypatch)
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(monkeypatch, provider="cerebras")

    asyncio.run(router.generate("prompt", stage="planner"))

    assert clock.sleeps == []


def test_cerebras_second_call_waits_for_min_interval(monkeypatch):
    clock = FakeClock(monkeypatch)
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(monkeypatch, provider="cerebras")

    asyncio.run(call_twice(router, stage="planner"))

    assert clock.sleeps == [20.0]


def test_cerebras_wait_uses_elapsed_time(monkeypatch):
    clock = FakeClock(monkeypatch)
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(monkeypatch, provider="cerebras")

    asyncio.run(router.generate("prompt", stage="planner"))
    clock.advance(7)
    asyncio.run(router.generate("prompt", stage="planner"))

    assert clock.sleeps == [13.0]


def test_invalid_min_interval_env_disables_pacing(monkeypatch):
    clock = FakeClock(monkeypatch)
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "not-a-number")
    router = make_router(monkeypatch, provider="cerebras")

    asyncio.run(call_twice(router, stage="planner"))

    assert clock.sleeps == []


def test_negative_min_interval_env_disables_pacing(monkeypatch):
    clock = FakeClock(monkeypatch)
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "-5")
    router = make_router(monkeypatch, provider="cerebras")

    asyncio.run(call_twice(router, stage="planner"))

    assert clock.sleeps == []


def test_groq_is_not_blocked_by_cerebras_pacing(monkeypatch):
    clock = FakeClock(monkeypatch)
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(
        monkeypatch,
        provider="groq",
        routing_mode="stage",
        planner="cerebras",
        generator="groq",
    )

    asyncio.run(router.generate("prompt", stage="planner"))
    asyncio.run(router.generate("prompt", stage="generator"))

    assert clock.sleeps == []
    assert FakeCerebrasProvider.calls == 1
    assert FakeGroqProvider.calls == 1


def test_groq_has_independent_pacing_env(monkeypatch):
    clock = FakeClock(monkeypatch)
    monkeypatch.setenv("GROQ_MIN_SECONDS_BETWEEN_CALLS", "11")
    router = make_router(monkeypatch, provider="groq")

    asyncio.run(call_twice(router, stage="generator"))

    assert clock.sleeps == [11.0]


def test_openrouter_has_independent_pacing_env(monkeypatch):
    clock = FakeClock(monkeypatch)
    monkeypatch.setenv("OPENROUTER_MIN_SECONDS_BETWEEN_CALLS", "9")
    router = make_router(monkeypatch, provider="openrouter")

    asyncio.run(call_twice(router, stage="reviewer"))

    assert clock.sleeps == [9.0]


def test_ollama_has_independent_pacing_env(monkeypatch):
    clock = FakeClock(monkeypatch)
    monkeypatch.setenv("OLLAMA_MIN_SECONDS_BETWEEN_CALLS", "8")
    router = make_router(monkeypatch, provider="ollama")

    asyncio.run(call_twice(router, stage="planner"))

    assert clock.sleeps == [8.0]


def test_pacing_applies_to_planner_generator_and_reviewer(monkeypatch):
    clock = FakeClock(monkeypatch)
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(monkeypatch, provider="cerebras")

    async def run_stages():
        await router.generate("prompt", stage="planner")
        await router.generate("prompt", stage="generator")
        await router.generate("prompt", stage="reviewer")

    asyncio.run(run_stages())

    assert clock.sleeps == [20.0, 20.0]


def test_stage_provider_mapping_still_routes_to_cerebras(monkeypatch):
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(
        monkeypatch,
        provider="groq",
        routing_mode="stage",
        planner="cerebras",
    )

    asyncio.run(router.generate("prompt", stage="planner"))

    assert FakeCerebrasProvider.calls == 1
    assert FakeGroqProvider.calls == 0


def test_strict_groq_ignores_cerebras_pacing(monkeypatch):
    clock = FakeClock(monkeypatch)
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(
        monkeypatch,
        provider="groq",
        strict="true",
        routing_mode="stage",
        planner="cerebras",
    )

    asyncio.run(call_twice(router, stage="planner"))

    assert clock.sleeps == []
    assert FakeGroqProvider.calls == 2
    assert FakeCerebrasProvider.calls == 0


def test_fallback_policy_still_allows_cerebras_after_groq_rate_limit(monkeypatch):
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(
        monkeypatch,
        provider="groq",
        policy="rate_limit_only",
        allowed="cerebras",
    )
    FakeGroqProvider.responses = [RateLimit429("429 rate limit")]

    asyncio.run(router.generate("prompt", stage="generator"))

    assert FakeGroqProvider.calls == 1
    assert FakeCerebrasProvider.calls == 1


def test_pacing_metadata_records_total_stage_and_provider(monkeypatch):
    FakeClock(monkeypatch)
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(monkeypatch, provider="cerebras")
    metadata = []

    asyncio.run(router.generate("prompt", stage="planner", metadata_recorder=metadata.append))
    asyncio.run(router.generate("prompt", stage="planner", metadata_recorder=metadata.append))

    assert metadata[-1]["provider_wait_seconds_total"] == 20.0
    assert metadata[-1]["provider_wait_by_stage"] == {"planner": 20.0}
    assert metadata[-1]["provider_wait_by_provider"] == {"cerebras": 20.0}


def test_call_llm_accumulates_provider_wait_metadata(monkeypatch):
    FakeClock(monkeypatch)
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(monkeypatch, provider="cerebras")
    monkeypatch.setattr(call_llm_module, "_router", router)

    async def run_calls():
        await call_llm_module.call_llm("prompt", stage="planner")
        await call_llm_module.call_llm("prompt", stage="generator")
        return request_provider_metadata_ctx.get()

    metadata = asyncio.run(run_calls())
    assert metadata["provider_wait_seconds_total"] == 20.0
    assert metadata["provider_wait_by_stage"] == {"generator": 20.0}
    assert metadata["provider_wait_by_provider"] == {"cerebras": 20.0}


def test_pacing_metadata_is_attached_to_rate_limit_records(monkeypatch):
    FakeClock(monkeypatch)
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(monkeypatch, provider="cerebras")
    metadata = []

    asyncio.run(router.generate("prompt", stage="planner", metadata_recorder=metadata.append))
    FakeCerebrasProvider.responses = [RateLimit429("429 rate limit")]
    with pytest.raises(RateLimit429):
        asyncio.run(router.generate("prompt", stage="planner", metadata_recorder=metadata.append))

    assert metadata[-1]["rate_limit_stage"] == "planner"
    assert metadata[-1]["provider_wait_seconds_total"] == 20.0


def test_eval_row_includes_provider_wait_metadata():
    budget = provider_budget()
    budget["provider_wait_seconds_total"] = 20.0
    budget["provider_wait_by_stage"] = {"generator": 20.0}
    budget["provider_wait_by_provider"] = {"cerebras": 20.0}

    row = row_from_budget(budget)

    assert row["provider_wait_seconds_total"] == 20.0
    assert row["provider_wait_by_stage_json"] == '{"generator": 20.0}'
    assert row["provider_wait_by_provider_json"] == '{"cerebras": 20.0}'


def test_eval_aggregate_includes_provider_wait_metadata():
    budget = provider_budget()
    budget["provider_wait_seconds_total"] = 20.0
    budget["provider_wait_by_stage"] = {"planner": 5.0, "generator": 15.0}
    budget["provider_wait_by_provider"] = {"cerebras": 20.0}

    report = aggregate_eval_rows([row_from_budget(budget)])

    assert report["provider_wait_seconds_total"] == 20.0
    assert report["provider_wait_by_stage"] == {"planner": 5.0, "generator": 15.0}
    assert report["provider_wait_by_provider"] == {"cerebras": 20.0}


def test_pacing_logs_provider_stage_and_wait(monkeypatch, caplog):
    FakeClock(monkeypatch)
    caplog.set_level("INFO", logger="app.shared.llm.llm_router")
    monkeypatch.setenv("CEREBRAS_MIN_SECONDS_BETWEEN_CALLS", "20")
    router = make_router(monkeypatch, provider="cerebras")

    asyncio.run(call_twice(router, stage="reviewer"))

    assert "event=LLM_PROVIDER_PACING provider=cerebras stage=reviewer wait_seconds=20.00" in caplog.text


def test_no_prompt_version_changes():
    prompt_text = Path("app/services/test_case_generation/prompts.py").read_text(
        encoding="utf-8"
    )

    assert 'TEST_CASE_GENERATOR_PROMPT_VERSION = "generator_v8"' in prompt_text
    assert 'TEST_CASE_REVIEWER_PROMPT_VERSION = "reviewer_v6"' in prompt_text


def test_no_new_provider_or_repairer_added():
    assert not Path("app/shared/llm/gemini_provider.py").exists()
    assert not Path("app/shared/llm/fireworks_provider.py").exists()
    assert not Path("app/shared/llm/litellm_provider.py").exists()
    assert not Path("app/services/test_case_generation/repairer.py").exists()

    router_text = Path("app/shared/llm/llm_router.py").read_text(encoding="utf-8")
    assert "TogetherProvider" not in router_text


def test_no_semantic_keyword_logic_added_to_pacing_files():
    combined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "app/shared/llm/llm_router.py",
            "app/shared/llm/call_llm.py",
        ]
    )

    assert "requirement" + ".lower(" not in combined
    assert 'if "' + "login" + '" in' not in combined
    assert 'if "' + "button" + '" in' not in combined
    assert 'if "' + "password" + '" in' not in combined
    assert "similarity" not in combined
    assert "fuzzy" not in combined


class FakeClock:
    def __init__(self, monkeypatch):
        self.current = 100.0
        self.sleeps = []
        monkeypatch.setattr(llm_router.time, "monotonic", self.monotonic)
        monkeypatch.setattr(llm_router.asyncio, "sleep", self.sleep)

    def monotonic(self):
        return self.current

    def advance(self, seconds):
        self.current += seconds

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.current += seconds


async def call_twice(router, stage):
    await router.generate("prompt", stage=stage)
    await router.generate("prompt", stage=stage)


def make_router(
    monkeypatch,
    provider="groq",
    strict="false",
    policy="none",
    allowed="",
    routing_mode="default",
    planner=None,
    generator=None,
    reviewer=None,
):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("LLM_STRICT_PROVIDER", strict)
    monkeypatch.setenv("LLM_FALLBACK_POLICY", policy)
    monkeypatch.setenv("LLM_ALLOWED_FALLBACKS", allowed)
    monkeypatch.setenv("LLM_PROVIDER_ROUTING_MODE", routing_mode)
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("CEREBRAS_API_KEY", "test")
    if planner is not None:
        monkeypatch.setenv("LLM_PLANNER_PROVIDER", planner)
    if generator is not None:
        monkeypatch.setenv("LLM_GENERATOR_PROVIDER", generator)
    if reviewer is not None:
        monkeypatch.setenv("LLM_REVIEWER_PROVIDER", reviewer)
    return llm_router.LLMRouter()


