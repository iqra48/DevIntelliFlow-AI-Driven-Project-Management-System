import os
import logging
import asyncio
import time
from typing import Callable, Optional

from .cerebras_provider import CerebrasProvider
from .groq_provider import GroqProvider
from .exceptions import (
    GroqGovernorLimitExceeded,
    ProviderFallbackUnavailable,
    StrictProviderFallbackBlocked,
)
from .model_config import DEFAULT_MODEL_CONFIG
from .openrouter_provider import OpenRouterProvider
from .ollama_provider import OllamaProvider
from .provider_governor import (
    ProviderGovernor,
    detect_groq_rate_limit_type,
    parse_retry_after_seconds,
)

logger = logging.getLogger(__name__)


def provider_min_interval_seconds(provider_name: str) -> float:
    env_by_provider = {
        "cerebras": "CEREBRAS_MIN_SECONDS_BETWEEN_CALLS",
        "groq": "GROQ_MIN_SECONDS_BETWEEN_CALLS",
        "openrouter": "OPENROUTER_MIN_SECONDS_BETWEEN_CALLS",
        "ollama": "OLLAMA_MIN_SECONDS_BETWEEN_CALLS",
    }
    env_name = env_by_provider.get(provider_name.casefold())
    if not env_name:
        return 0.0
    try:
        value = float(os.getenv(env_name, "0") or "0")
    except ValueError:
        return 0.0
    return value if value > 0 else 0.0


def is_strict_groq_mode() -> bool:
    configured = os.getenv("LLM_PROVIDER", "ollama").strip().casefold()
    strict = os.getenv("LLM_STRICT_PROVIDER", "false").strip().casefold()
    return configured == "groq" and strict in {"true", "1", "yes"}


def configured_provider_name() -> str:
    return os.getenv("LLM_PROVIDER", "groq").strip().casefold()


def strict_provider_value() -> bool:
    return os.getenv("LLM_STRICT_PROVIDER", "false").strip().casefold() in {
        "true",
        "1",
        "yes",
    }


def fallback_policy() -> str:
    policy = os.getenv("LLM_FALLBACK_POLICY", "none").strip().casefold()
    allowed = {"none", "rate_limit_only", "provider_failure_only", "any_failure"}
    if policy not in allowed:
        return "none"
    return policy


def allowed_fallbacks() -> list[str]:
    raw = os.getenv("LLM_ALLOWED_FALLBACKS", "")
    output = []
    for item in raw.split(","):
        name = item.strip().casefold()
        if name and name not in output:
            output.append(name)
    return output


def provider_routing_mode() -> str:
    mode = os.getenv("LLM_PROVIDER_ROUTING_MODE", "default").strip().casefold()
    return "stage" if mode == "stage" else "default"


def stage_provider_name(stage: str | None, default_provider: str) -> str:
    if provider_routing_mode() != "stage":
        return default_provider
    env_by_stage = {
        "planner": "LLM_PLANNER_PROVIDER",
        "generator": "LLM_GENERATOR_PROVIDER",
        "reviewer": "LLM_REVIEWER_PROVIDER",
    }
    env_name = env_by_stage.get(stage or "")
    if not env_name:
        return default_provider
    return os.getenv(env_name, default_provider).strip().casefold() or default_provider


def is_rate_limit_exception(exc: Exception) -> bool:
    text = str(exc).casefold()
    if getattr(exc, "status_code", None) == 429:
        return True
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 429:
        return True
    if getattr(exc, "code", None) == 429:
        return True
    return (
        "ratelimit" in type(exc).__name__.casefold()
        or "rate limit" in text
        or "rate_limit" in text
        or "429" in text
        or "quota" in text
    )


class LLMRouter:
    """
    Production inference router.

    Responsible for selecting which LLM provider
    should execute a request.
    """

    def __init__(self):
        self.governor = ProviderGovernor()
        self.strict_groq_only = is_strict_groq_mode()
        self.primary_provider = configured_provider_name()
        self.strict_provider = strict_provider_value()
        self.policy = fallback_policy()
        self.allowed_fallback_names = allowed_fallbacks()
        self.routing_mode = provider_routing_mode()
        self.provider_classes = self._provider_classes()
        self.providers = self._build_provider_chain()
        self.provider_by_name = {
            self._provider_key(provider): provider for provider in self.providers
        }
        self._provider_pacing_locks: dict[str, asyncio.Lock] = {}
        self._provider_last_call_started_at: dict[str, float] = {}

        if not self.providers:
            raise RuntimeError("No LLM providers could be initialized")

        provider_names = ", ".join(provider.__class__.__name__ for provider in self.providers)
        logger.info(f"LLMRouter initialized with providers={provider_names}")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        num_predict: Optional[int] = None,
        stage: str | None = None,
        metadata_recorder: Callable[[dict], None] | None = None,
    ) -> str:
        config = DEFAULT_MODEL_CONFIG
        selected_model = model or config.model
        selected_num_predict = num_predict or config.num_predict

        last_error = None
        retry_attempts = 0
        primary_attempted = False
        metadata_base = {
            "stage": stage or "unknown",
            "primary_provider": self.primary_provider,
            "strict_provider": self.strict_provider,
            "provider_role_map": self._provider_role_map(),
            "fallback_used": False,
            "fallback_provider": None,
            "fallback_reason": None,
            "rate_limit_stage": None,
            "rate_limit_type": None,
            "retry_attempts": 0,
            "provider_wait_seconds_total": 0.0,
            "provider_wait_by_stage": {},
            "provider_wait_by_provider": {},
        }

        def record(**updates):
            if metadata_recorder is None:
                return
            payload = dict(metadata_base)
            payload.update(updates)
            metadata_recorder(payload)

        for provider_name in self._ordered_provider_keys_for_stage(stage):
            provider = self.provider_by_name.get(provider_name)
            if provider is None:
                if provider_name not in self.provider_classes:
                    raise RuntimeError(f"Unsupported LLM provider for stage {stage}: {provider_name}")
                if provider_name == self._stage_primary_provider(stage):
                    raise RuntimeError(
                        f"Provider {provider_name} is not configured for stage {stage}"
                    )
                continue
            provider_name = self._provider_key(provider)
            is_primary_attempt = not primary_attempted
            primary_attempted = True
            if isinstance(provider, GroqProvider):
                estimated_tokens = self.governor.estimate_tokens(
                    prompt,
                    selected_num_predict,
                    system_prompt,
                )
                allowed, reason = self.governor.can_use_groq(estimated_tokens)
                if not allowed:
                    if self.strict_groq_only:
                        logger.warning(
                            "event=GROQ_ONLY_BLOCKED_BY_GOVERNOR reason=%s",
                            reason,
                        )
                        raise GroqGovernorLimitExceeded(reason)
                    if not self._fallback_allowed_for_error(
                        GroqGovernorLimitExceeded(reason)
                    ):
                        record(
                            provider_used=provider_name,
                            rate_limit_stage=stage or "unknown",
                            rate_limit_type="TPD",
                        )
                        raise GroqGovernorLimitExceeded(reason)
                    logger.warning("Groq unavailable by governor. Trying allowed fallback.")
                    continue
            else:
                estimated_tokens = None

            provider_model = self._resolve_model(provider, selected_model)
            started_at = time.perf_counter()

            logger.info(
                "LLM attempt provider=%s model=%s num_predict=%s",
                provider.__class__.__name__,
                provider_model,
                selected_num_predict,
            )

            try:
                (
                    result,
                    attempt_retries,
                    provider_wait_seconds_total,
                    provider_wait_by_stage,
                    provider_wait_by_provider,
                ) = await self._generate_with_optional_retry(
                    provider,
                    provider_name,
                    prompt,
                    system_prompt,
                    provider_model,
                    selected_num_predict,
                    stage or "unknown",
                )
                retry_attempts = attempt_retries
                elapsed = time.perf_counter() - started_at
                if isinstance(provider, GroqProvider) and estimated_tokens is not None:
                    self.governor.record_groq_usage(estimated_tokens)
                logger.info(
                    "LLM success provider=%s elapsed=%.2fs",
                    provider.__class__.__name__,
                    elapsed,
                )
                fallback_used = not is_primary_attempt
                record(
                    provider_used=provider_name,
                    provider_used_by_stage={stage or "unknown": provider_name},
                    fallback_used=fallback_used,
                    fallback_provider=provider_name if fallback_used else None,
                    fallback_reason=str(last_error) if fallback_used and last_error else None,
                    retry_attempts=retry_attempts,
                    provider_wait_seconds_total=provider_wait_seconds_total,
                    provider_wait_by_stage=provider_wait_by_stage,
                    provider_wait_by_provider=provider_wait_by_provider,
                )
                return result
            except Exception as exc:
                last_error = exc
                elapsed = time.perf_counter() - started_at
                retry_attempts = getattr(exc, "_llm_retry_attempts", retry_attempts)
                rate_limit_type = (
                    detect_groq_rate_limit_type(str(exc))
                    if is_rate_limit_exception(exc)
                    else None
                )
                if is_rate_limit_exception(exc):
                    record(
                        provider_used=provider_name,
                        rate_limit_stage=stage or "unknown",
                        rate_limit_type=rate_limit_type,
                        retry_attempts=retry_attempts,
                        provider_wait_seconds_total=getattr(
                            exc, "_llm_provider_wait_seconds_total", 0.0
                        ),
                        provider_wait_by_stage=getattr(
                            exc, "_llm_provider_wait_by_stage", {}
                        ),
                        provider_wait_by_provider=getattr(
                            exc, "_llm_provider_wait_by_provider", {}
                        ),
                    )

                if isinstance(provider, GroqProvider):
                    self.governor.record_groq_failure(exc)

                logger.warning(
                    "Provider %s failed after %.2fs: %s: %s",
                    provider.__class__.__name__,
                    elapsed,
                    type(exc).__name__,
                    exc,
                )

                if self.strict_groq_only:
                    logger.warning(
                        "event=GROQ_ONLY_PROVIDER_FAILED provider=%s error_type=%s",
                        provider.__class__.__name__,
                        type(exc).__name__,
                    )
                    raise StrictProviderFallbackBlocked(
                        "Groq-only provider failed; fallback providers are disabled. "
                        f"Original error [{type(exc).__name__}]: {exc}"
                    ) from exc

                if not self._fallback_allowed_for_error(exc):
                    raise

        if self.policy != "none" and self.allowed_fallback_names:
            raise ProviderFallbackUnavailable(
                "Allowed fallback provider is not available or not configured; "
                f"fallback_policy={self.policy} "
                f"allowed_fallbacks={','.join(self.allowed_fallback_names)} "
                f"primary_error={last_error}"
            ) from last_error

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    def _build_provider_chain(self) -> list:
        provider_classes = self.provider_classes
        preferred = self.primary_provider

        if preferred not in provider_classes:
            raise RuntimeError(f"Unsupported LLM provider: {preferred}")

        if self.strict_groq_only and preferred == "groq":
            ordered_keys = ["groq"]
        else:
            ordered_keys = []
            for key in [preferred] + self.allowed_fallback_names + list(self._provider_role_map().values()):
                if key and key in provider_classes and key not in ordered_keys:
                    ordered_keys.append(key)

        providers = []

        for key in ordered_keys:
            provider_class = provider_classes[key]

            try:
                providers.append(provider_class())
            except Exception as exc:
                logger.info(f"Skipping provider {provider_class.__name__}: {exc}")

        return providers

    def _provider_classes(self) -> dict:
        return {
            "cerebras": CerebrasProvider,
            "groq": GroqProvider,
            "openrouter": OpenRouterProvider,
            "ollama": OllamaProvider,
        }

    def _stage_primary_provider(self, stage: str | None) -> str:
        if self.strict_groq_only and self.primary_provider == "groq":
            return "groq"
        return stage_provider_name(stage, self.primary_provider)

    def _provider_role_map(self) -> dict[str, str]:
        if self.strict_groq_only and self.primary_provider == "groq":
            return {"planner": "groq", "generator": "groq", "reviewer": "groq"}
        return {
            "planner": stage_provider_name("planner", self.primary_provider),
            "generator": stage_provider_name("generator", self.primary_provider),
            "reviewer": stage_provider_name("reviewer", self.primary_provider),
        }

    def _ordered_provider_keys_for_stage(self, stage: str | None) -> list[str]:
        primary = self._stage_primary_provider(stage)
        if primary not in self.provider_classes:
            raise RuntimeError(f"Unsupported LLM provider for stage {stage}: {primary}")
        if self.strict_groq_only and self.primary_provider == "groq":
            return ["groq"]
        output = [primary]
        if self.policy != "none":
            output.extend(
                key
                for key in self.allowed_fallback_names
                if key in self.provider_classes and key != primary
            )
        return output

    def _fallback_allowed_for_error(self, exc: Exception) -> bool:
        if self.strict_groq_only:
            return False
        if not self.allowed_fallback_names:
            return False
        policy = self.policy
        if policy == "none":
            return False
        if policy == "any_failure":
            return True
        if policy == "rate_limit_only":
            return is_rate_limit_exception(exc)
        if policy == "provider_failure_only":
            return not is_rate_limit_exception(exc)
        return False

    async def _generate_with_optional_retry(
        self,
        provider,
        provider_name: str,
        prompt: str,
        system_prompt: str | None,
        model: str,
        num_predict: int,
        stage: str,
    ) -> tuple[str, int, float, dict[str, float], dict[str, float]]:
        wait_total = 0.0
        wait_by_stage: dict[str, float] = {}
        wait_by_provider: dict[str, float] = {}

        def record_wait(wait_seconds: float) -> None:
            nonlocal wait_total
            if wait_seconds <= 0:
                return
            wait_total += wait_seconds
            wait_by_stage[stage] = wait_by_stage.get(stage, 0.0) + wait_seconds
            wait_by_provider[provider_name] = (
                wait_by_provider.get(provider_name, 0.0) + wait_seconds
            )

        def attach_wait_metadata(exc: Exception) -> None:
            setattr(exc, "_llm_provider_wait_seconds_total", wait_total)
            setattr(exc, "_llm_provider_wait_by_stage", dict(wait_by_stage))
            setattr(exc, "_llm_provider_wait_by_provider", dict(wait_by_provider))

        try:
            record_wait(await self._pace_provider_call(provider_name, stage))
            result = await provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                num_predict=num_predict,
            )
            return result, 0, wait_total, wait_by_stage, wait_by_provider
        except Exception as exc:
            if not isinstance(provider, GroqProvider) or self.strict_groq_only:
                attach_wait_metadata(exc)
                raise
            if not is_rate_limit_exception(exc):
                attach_wait_metadata(exc)
                raise
            retry_after = parse_retry_after_seconds(str(exc))
            max_retry_after = float(os.getenv("LLM_MAX_RETRY_AFTER_SECONDS", "0") or "0")
            if retry_after is None or retry_after > max_retry_after:
                setattr(exc, "_llm_retry_attempts", 0)
                attach_wait_metadata(exc)
                raise
            logger.warning(
                "Groq rate limit retry stage=%s retry_after=%.2fs",
                stage,
                retry_after,
            )
            await asyncio.sleep(retry_after)
            try:
                record_wait(await self._pace_provider_call(provider_name, stage))
                result = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=model,
                    num_predict=num_predict,
                )
                return result, 1, wait_total, wait_by_stage, wait_by_provider
            except Exception as retry_exc:
                setattr(retry_exc, "_llm_retry_attempts", 1)
                attach_wait_metadata(retry_exc)
                raise

    async def _pace_provider_call(self, provider_name: str, stage: str) -> float:
        min_interval = provider_min_interval_seconds(provider_name)
        if min_interval <= 0:
            return 0.0

        lock = self._provider_pacing_locks.setdefault(provider_name, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            last_started = self._provider_last_call_started_at.get(provider_name)
            wait_seconds = 0.0
            if last_started is not None:
                elapsed = now - last_started
                wait_seconds = max(0.0, min_interval - elapsed)
            if wait_seconds > 0:
                logger.info(
                    "event=LLM_PROVIDER_PACING provider=%s stage=%s wait_seconds=%.2f",
                    provider_name,
                    stage,
                    wait_seconds,
                )
                await asyncio.sleep(wait_seconds)
            self._provider_last_call_started_at[provider_name] = time.monotonic()
            return wait_seconds

    def _provider_key(self, provider) -> str:
        if isinstance(provider, GroqProvider):
            return "groq"
        if isinstance(provider, OpenRouterProvider):
            return "openrouter"
        if isinstance(provider, OllamaProvider):
            return "ollama"
        if isinstance(provider, CerebrasProvider):
            return "cerebras"
        return provider.__class__.__name__.casefold()

    def _resolve_model(self, provider, requested_model: str) -> str:
        if isinstance(provider, GroqProvider):
            return os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

        if isinstance(provider, OpenRouterProvider):
            return os.getenv(
                "OPENROUTER_MODEL",
                "meta-llama/llama-3.1-8b-instruct",
            )

        if isinstance(provider, OllamaProvider):
            return os.getenv(
                "OLLAMA_MODEL",
                "llama3.1:8b-instruct-q4_K_M",
            )

        if isinstance(provider, CerebrasProvider):
            return os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")

        return requested_model
