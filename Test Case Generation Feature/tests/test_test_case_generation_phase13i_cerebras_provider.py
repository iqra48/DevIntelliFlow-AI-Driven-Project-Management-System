import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.services.test_case_generation.cache import clear_test_case_cache
from app.services.test_case_generation.models import (
    RequirementForTestCase,
    RequirementReviewResult,
    TestCaseBundle,
)
from app.services.test_case_generation.orchestrator import TestCaseEngine
from app.shared.llm import call_llm as call_llm_module
from app.shared.llm import cerebras_provider, llm_router
from app.shared.llm.cerebras_provider import CerebrasProvider
from app.shared.llm.exceptions import ProviderFallbackUnavailable


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {
            "choices": [{"message": {"content": "CEREBRAS_OK"}}],
            "data": [],
        }
        self.request = httpx.Request("POST", "https://api.cerebras.ai/v1/chat/completions")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("HTTP error", request=self.request, response=self)


class FakeAsyncClient:
    posts = []
    gets = []
    response = FakeResponse()

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None):
        self.__class__.posts.append({"url": url, "headers": headers, "json": json})
        return self.__class__.response

    async def get(self, url, headers=None):
        self.__class__.gets.append({"url": url, "headers": headers})
        return self.__class__.response


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


class FakeCerebrasProvider:
    calls = 0

    def __init__(self):
        pass

    async def generate(self, **kwargs):
        type(self).calls += 1
        return "{}"


class FakeOllamaProvider(FakeCerebrasProvider):
    pass


class FakeOpenRouterProvider(FakeCerebrasProvider):
    pass


class RateLimit429(Exception):
    status_code = 429


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    clear_test_case_cache()
    monkeypatch.delenv("LLM_PROVIDER_ROUTING_MODE", raising=False)
    monkeypatch.delenv("LLM_PLANNER_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_GENERATOR_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_REVIEWER_PROVIDER", raising=False)
    FakeAsyncClient.posts = []
    FakeAsyncClient.gets = []
    FakeAsyncClient.response = FakeResponse()
    FakeGroqProvider.calls = 0
    FakeGroqProvider.responses = []
    FakeCerebrasProvider.calls = 0
    FakeOllamaProvider.calls = 0
    FakeOpenRouterProvider.calls = 0
    monkeypatch.setattr(cerebras_provider.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(llm_router, "GroqProvider", FakeGroqProvider)
    monkeypatch.setattr(llm_router, "CerebrasProvider", FakeCerebrasProvider)
    monkeypatch.setattr(llm_router, "OllamaProvider", FakeOllamaProvider)
    monkeypatch.setattr(llm_router, "OpenRouterProvider", FakeOpenRouterProvider)
    monkeypatch.setattr(call_llm_module, "_router", None)
    yield
    clear_test_case_cache()


def test_cerebras_provider_default_model_is_gpt_oss_120b(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "test")

    asyncio.run(CerebrasProvider().generate("hello"))

    assert FakeAsyncClient.posts[0]["json"]["model"] == "gpt-oss-120b"


def test_cerebras_provider_uses_cerebras_model_when_set(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "test")
    monkeypatch.setenv("CEREBRAS_MODEL", "custom-model")

    asyncio.run(CerebrasProvider().generate("hello"))

    assert FakeAsyncClient.posts[0]["json"]["model"] == "custom-model"


def test_cerebras_provider_builds_openai_compatible_messages(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "test")

    asyncio.run(CerebrasProvider().generate("user", system_prompt="system"))

    assert FakeAsyncClient.posts[0]["json"]["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]


def test_cerebras_provider_maps_num_predict_to_max_output_tokens(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "test")
    monkeypatch.setenv("CEREBRAS_MIN_OUTPUT_TOKENS", "0")

    asyncio.run(CerebrasProvider().generate("hello", num_predict=123))

    assert FakeAsyncClient.posts[0]["json"]["max_completion_tokens"] == 123


def test_cerebras_provider_returns_assistant_content(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "test")

    assert asyncio.run(CerebrasProvider().generate("hello")) == "CEREBRAS_OK"


def test_cerebras_provider_missing_content_raises_provider_error(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "test")
    FakeAsyncClient.response = FakeResponse(payload={"choices": [{"message": {}}]})

    with pytest.raises(RuntimeError, match="missing assistant content"):
        asyncio.run(CerebrasProvider().generate("hello"))


def test_cerebras_provider_429_is_classified_as_rate_limit(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "test")
    FakeAsyncClient.response = FakeResponse(status_code=429)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        asyncio.run(CerebrasProvider().generate("hello"))

    assert llm_router.is_rate_limit_exception(exc_info.value) is True


def test_router_supports_llm_provider_cerebras(monkeypatch):
    router = make_router(monkeypatch, provider="cerebras")

    assert [type(provider).__name__ for provider in router.providers] == ["FakeCerebrasProvider"]


def test_router_includes_cerebras_only_when_explicit(monkeypatch):
    router = make_router(monkeypatch, provider="groq")

    assert "cerebras" not in router.provider_by_name


def test_strict_groq_mode_ignores_stage_provider_env_vars(monkeypatch):
    router = make_router(
        monkeypatch,
        provider="groq",
        strict="true",
        routing_mode="stage",
        planner="cerebras",
        generator="cerebras",
        reviewer="cerebras",
    )

    assert router._provider_role_map() == {
        "planner": "groq",
        "generator": "groq",
        "reviewer": "groq",
    }


def test_strict_groq_mode_still_builds_only_groq(monkeypatch):
    router = make_router(monkeypatch, provider="groq", strict="true", allowed="cerebras")

    assert [type(provider).__name__ for provider in router.providers] == ["FakeGroqProvider"]


def test_stage_routing_planner_cerebras_uses_cerebras(monkeypatch):
    router = make_router(monkeypatch, routing_mode="stage", planner="cerebras")

    asyncio.run(router.generate("prompt", stage="planner"))

    assert FakeCerebrasProvider.calls == 1


def test_stage_routing_generator_groq_uses_groq(monkeypatch):
    router = make_router(monkeypatch, routing_mode="stage", generator="groq")

    asyncio.run(router.generate("prompt", stage="generator"))

    assert FakeGroqProvider.calls == 1


def test_stage_routing_reviewer_cerebras_uses_cerebras(monkeypatch):
    router = make_router(monkeypatch, routing_mode="stage", reviewer="cerebras")

    asyncio.run(router.generate("prompt", stage="reviewer"))

    assert FakeCerebrasProvider.calls == 1


def test_missing_stage_env_falls_back_to_llm_provider(monkeypatch):
    router = make_router(monkeypatch, provider="cerebras", routing_mode="stage")

    asyncio.run(router.generate("prompt", stage="planner"))

    assert FakeCerebrasProvider.calls == 1


def test_unsupported_stage_provider_raises_clear_error(monkeypatch):
    router = make_router(monkeypatch, routing_mode="stage", planner="notreal")

    with pytest.raises(RuntimeError, match="Unsupported LLM provider"):
        asyncio.run(router.generate("prompt", stage="planner"))


def test_provider_used_by_stage_records_all_stages(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "cerebras")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "false")
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.budget.provider_used_by_stage == {
        "planner": "cerebras",
        "generator": "cerebras",
        "reviewer": "cerebras",
    }


def test_cerebras_only_records_primary_provider_and_no_fallback(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "cerebras")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "false")

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.budget.primary_provider == "cerebras"
    assert result.budget.fallback_used is False


def test_hybrid_mode_records_stage_provider_map(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_STRICT_PROVIDER", "false")
    monkeypatch.setenv("LLM_PROVIDER_ROUTING_MODE", "stage")
    monkeypatch.setenv("LLM_PLANNER_PROVIDER", "cerebras")
    monkeypatch.setenv("LLM_GENERATOR_PROVIDER", "groq")
    monkeypatch.setenv("LLM_REVIEWER_PROVIDER", "cerebras")
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.plan_batch", fake_plan_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.generate_batch", fake_generate_batch)
    monkeypatch.setattr("app.services.test_case_generation.orchestrator.review_batch", fake_review_batch)

    result = asyncio.run(TestCaseEngine().generate([raw_requirement()]))

    assert result.budget.provider_role_map == {
        "planner": "cerebras",
        "generator": "groq",
        "reviewer": "cerebras",
    }


def test_groq_rate_limit_can_fallback_to_cerebras_when_policy_allows(monkeypatch):
    router = make_router(
        monkeypatch,
        provider="groq",
        strict="false",
        policy="rate_limit_only",
        allowed="cerebras",
    )
    FakeGroqProvider.responses = [RateLimit429("Rate limit reached")]

    asyncio.run(router.generate("prompt", stage="generator"))

    assert FakeGroqProvider.calls == 1
    assert FakeCerebrasProvider.calls == 1


def test_provider_failure_does_not_fallback_when_policy_is_rate_limit_only(monkeypatch):
    router = make_router(
        monkeypatch,
        provider="groq",
        strict="false",
        policy="rate_limit_only",
        allowed="cerebras",
    )
    FakeGroqProvider.responses = [RuntimeError("network failed")]

    with pytest.raises(RuntimeError):
        asyncio.run(router.generate("prompt", stage="generator"))

    assert FakeCerebrasProvider.calls == 0


def test_health_cerebras_returns_configured_false_when_key_missing(monkeypatch):
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    response = TestClient(main.app).get("/health/cerebras")

    assert response.status_code == 200
    assert response.json()["configured"] is False


def test_health_cerebras_does_not_break_health_groq():
    routes = {route.path for route in main.app.routes}

    assert "/health/cerebras" in routes
    assert "/health/groq" in routes


def test_no_forbidden_provider_added():
    assert not Path("app/shared/llm/gemini_provider.py").exists()
    assert not Path("app/shared/llm/fireworks_provider.py").exists()
    assert not Path("app/shared/llm/litellm_provider.py").exists()
    assert not Path("app/shared/llm/openai_provider.py").exists()


def test_no_repairer_py():
    assert not Path("app/services/test_case_generation/repairer.py").exists()


def test_no_approved_status():
    assert "APPROVED" not in Path("app/services/test_case_generation/models.py").read_text(
        encoding="utf-8"
    )


def test_no_prompt_version_changes():
    prompt_text = Path("app/services/test_case_generation/prompts.py").read_text(
        encoding="utf-8"
    )

    assert 'TEST_CASE_GENERATOR_PROMPT_VERSION = "generator_v8"' in prompt_text
    assert 'TEST_CASE_REVIEWER_PROMPT_VERSION = "reviewer_v6"' in prompt_text


def test_no_semantic_keyword_logic():
    combined = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in [
            "app/shared/llm/cerebras_provider.py",
            "app/shared/llm/llm_router.py",
            "app/shared/llm/call_llm.py",
        ]
    )

    assert "requirement" + ".lower(" not in combined
    assert 'if "' + "login" + '" in' not in combined
    assert "fuzzy" not in combined
    assert "similarity" not in combined
    assert "contains(" not in combined
    assert "startswith(" not in combined


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
    if planner is not None:
        monkeypatch.setenv("LLM_PLANNER_PROVIDER", planner)
    if generator is not None:
        monkeypatch.setenv("LLM_GENERATOR_PROVIDER", generator)
    if reviewer is not None:
        monkeypatch.setenv("LLM_REVIEWER_PROVIDER", reviewer)
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("CEREBRAS_API_KEY", "test")
    return llm_router.LLMRouter()


def raw_requirement():
    return {
        "id": "REQ_1",
        "requirement": "The system shall process item REQ_1.",
        "classification_type": "FR",
    }


async def fake_plan_batch(requirements, project_context=None, mode="mvp_fast"):
    from app.shared.llm.provider_metadata import request_provider_metadata_ctx

    metadata = request_provider_metadata_ctx.get()
    metadata["provider_used_by_stage"]["planner"] = metadata["provider_role_map"].get(
        "planner", metadata["primary_provider"]
    )
    req = requirements[0]
    from tests.test_test_case_generation_phase6_orchestrator import plan_for

    return {req.id: plan_for(req)}


async def fake_generate_batch(requirements, plans, project_context=None, mode="mvp_fast"):
    from app.shared.llm.provider_metadata import request_provider_metadata_ctx
    from tests.test_test_case_generation_phase6_orchestrator import bundle_for, case_for

    metadata = request_provider_metadata_ctx.get()
    metadata["provider_used_by_stage"]["generator"] = metadata["provider_role_map"].get(
        "generator", metadata["primary_provider"]
    )
    req = requirements[0]
    return {req.id: bundle_for(req, [case_for(req)])}


async def fake_review_batch(requirements, plans, bundles, project_context=None, mode="mvp_fast"):
    from app.shared.llm.provider_metadata import request_provider_metadata_ctx
    from tests.test_test_case_generation_phase13a_reviewer_filter import decision_payload

    metadata = request_provider_metadata_ctx.get()
    metadata["provider_used_by_stage"]["reviewer"] = metadata["provider_role_map"].get(
        "reviewer", metadata["primary_provider"]
    )
    req = requirements[0]
    bundle = bundles[req.id]
    return {
        req.id: RequirementReviewResult(
            requirement_id=req.id,
            decisions=[
                _decision_from_payload(req.id, decision_payload(case.test_case_id, "KEEP"))
                for case in bundle.test_cases
            ],
            warnings=[],
        )
    }


def _decision_from_payload(requirement_id, payload):
    from app.services.test_case_generation.models import TestCaseReviewDecision

    return TestCaseReviewDecision(
        requirement_id=requirement_id,
        test_case_id=payload["test_case_id"],
        decision=payload["decision"],
        reason=payload["reason"],
        unsupported_elements=payload["unsupported_elements"],
        required_human_review=payload["required_human_review"],
    )


