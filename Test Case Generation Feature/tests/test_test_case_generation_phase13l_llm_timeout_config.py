import asyncio
from pathlib import Path

from app.shared.llm import call_llm as call_llm_module
from app.shared.llm.provider_metadata import request_provider_metadata_ctx


def test_default_llm_call_timeout_seconds_returns_120(monkeypatch):
    monkeypatch.delenv("LLM_CALL_TIMEOUT_SECONDS", raising=False)

    assert call_llm_module.llm_call_timeout_seconds() == 120.0


def test_configured_llm_call_timeout_seconds_returns_value(monkeypatch):
    monkeypatch.setenv("LLM_CALL_TIMEOUT_SECONDS", "90")

    assert call_llm_module.llm_call_timeout_seconds() == 90.0


def test_invalid_llm_call_timeout_seconds_falls_back_to_120(monkeypatch):
    monkeypatch.setenv("LLM_CALL_TIMEOUT_SECONDS", "not-a-number")

    assert call_llm_module.llm_call_timeout_seconds() == 120.0


def test_zero_timeout_falls_back_to_120(monkeypatch):
    monkeypatch.setenv("LLM_CALL_TIMEOUT_SECONDS", "0")

    assert call_llm_module.llm_call_timeout_seconds() == 120.0


def test_negative_timeout_falls_back_to_120(monkeypatch):
    monkeypatch.setenv("LLM_CALL_TIMEOUT_SECONDS", "-5")

    assert call_llm_module.llm_call_timeout_seconds() == 120.0


def test_non_strict_call_llm_passes_configured_timeout_to_execute_with_retry(monkeypatch):
    calls = []

    async def fake_generate(**kwargs):
        metadata_recorder = kwargs.get("metadata_recorder")
        if metadata_recorder:
            metadata_recorder(
                {
                    "primary_provider": "cerebras",
                    "strict_provider": False,
                    "provider_used_by_stage": {"planner": "cerebras"},
                    "provider_role_map": {"planner": "cerebras"},
                }
            )
        return "{}"

    async def fake_execute_with_retry(fn, retries, timeout, *args, **kwargs):
        calls.append({"retries": retries, "timeout": timeout})
        return await fn(**kwargs)

    monkeypatch.setenv("LLM_PROVIDER", "cerebras")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "false")
    monkeypatch.setenv("LLM_CALL_TIMEOUT_SECONDS", "90")
    monkeypatch.setattr(call_llm_module, "execute_with_retry", fake_execute_with_retry)
    monkeypatch.setattr(call_llm_module, "_get_router", lambda: FakeRouter(fake_generate))

    result = asyncio.run(call_llm_module.call_llm("prompt", stage="planner"))

    assert result == "{}"
    assert calls == [{"retries": 0, "timeout": 90.0}]


def test_strict_groq_path_bypasses_execute_with_retry(monkeypatch):
    execute_calls = []
    router_calls = []

    async def fake_generate(**kwargs):
        router_calls.append(kwargs)
        return "{}"

    async def fake_execute_with_retry(*args, **kwargs):
        execute_calls.append(kwargs)
        return "{}"

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "true")
    monkeypatch.setenv("LLM_CALL_TIMEOUT_SECONDS", "90")
    monkeypatch.setattr(call_llm_module, "execute_with_retry", fake_execute_with_retry)
    monkeypatch.setattr(call_llm_module, "_get_router", lambda: FakeRouter(fake_generate))

    result = asyncio.run(call_llm_module.call_llm("prompt", stage="planner"))

    assert result == "{}"
    assert execute_calls == []
    assert len(router_calls) == 1


def test_provider_metadata_recording_still_works(monkeypatch):
    async def fake_generate(**kwargs):
        kwargs["metadata_recorder"](
            {
                "primary_provider": "groq",
                "strict_provider": False,
                "provider_used_by_stage": {"generator": "groq"},
                "provider_role_map": {"generator": "groq"},
                "provider_wait_seconds_total": 30.0,
                "provider_wait_by_stage": {"generator": 30.0},
                "provider_wait_by_provider": {"groq": 30.0},
            }
        )
        return "{}"

    async def fake_execute_with_retry(fn, retries, timeout, *args, **kwargs):
        return await fn(**kwargs)

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "false")
    monkeypatch.setattr(call_llm_module, "execute_with_retry", fake_execute_with_retry)
    monkeypatch.setattr(call_llm_module, "_get_router", lambda: FakeRouter(fake_generate))

    async def run_call():
        await call_llm_module.call_llm("prompt", stage="generator")
        return request_provider_metadata_ctx.get()

    metadata = asyncio.run(run_call())

    assert metadata["provider_used_by_stage"] == {"generator": "groq"}
    assert metadata["provider_wait_seconds_total"] == 30.0
    assert metadata["provider_wait_by_stage"] == {"generator": 30.0}
    assert metadata["provider_wait_by_provider"] == {"groq": 30.0}


def test_no_provider_routing_behavior_changed():
    router_text = Path("app/shared/llm/llm_router.py").read_text(encoding="utf-8")

    assert "def _ordered_provider_keys_for_stage" in router_text
    assert "def _fallback_allowed_for_error" in router_text


def test_no_provider_pacing_behavior_changed():
    router_text = Path("app/shared/llm/llm_router.py").read_text(encoding="utf-8")

    assert "def _pace_provider_call" in router_text
    assert "event=LLM_PROVIDER_PACING" in router_text
    assert "CEREBRAS_MIN_SECONDS_BETWEEN_CALLS" in router_text


def test_no_prompt_version_changes():
    prompt_text = Path("app/services/test_case_generation/prompts.py").read_text(
        encoding="utf-8"
    )

    assert 'TEST_CASE_GENERATOR_PROMPT_VERSION = "generator_v8"' in prompt_text
    assert 'TEST_CASE_REVIEWER_PROMPT_VERSION = "reviewer_v6"' in prompt_text


def test_no_repairer_py():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_no_approved_status():
    assert "APPROVED" not in Path("app/services/test_case_generation/models.py").read_text(
        encoding="utf-8"
    )


def test_no_semantic_keyword_logic():
    combined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
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


class FakeRouter:
    def __init__(self, generate_fn):
        self.generate_fn = generate_fn

    async def generate(self, **kwargs):
        return await self.generate_fn(**kwargs)


