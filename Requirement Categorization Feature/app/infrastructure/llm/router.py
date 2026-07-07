import os
import logging
import time
from typing import Optional

from .groq_provider import GroqProvider
from .config import DEFAULT_MODEL_CONFIG
from .rate_limiter import ProviderGovernor

logger = logging.getLogger(__name__)


class LLMRouter:
    """
    Production inference router.

    Responsible for selecting which LLM provider
    should execute a request.
    """

    def __init__(self):
        self.governor = ProviderGovernor()
        self.providers = self._build_provider_chain()

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
    ) -> str:
        config = DEFAULT_MODEL_CONFIG
        selected_model = model or config.model
        selected_num_predict = num_predict or config.num_predict

        last_error = None

        for provider in self.providers:
            if isinstance(provider, GroqProvider):
                if not self.governor.allow_groq(prompt, selected_num_predict, system_prompt):
                    raise RuntimeError("Groq unavailable by governor")

            provider_model = self._resolve_model(provider, selected_model)
            started_at = time.perf_counter()

            logger.info(
                "LLM attempt provider=%s model=%s num_predict=%s",
                provider.__class__.__name__,
                provider_model,
                selected_num_predict,
            )

            try:
                result = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=provider_model,
                    num_predict=selected_num_predict,
                )
                elapsed = time.perf_counter() - started_at
                logger.info(
                    "LLM success provider=%s elapsed=%.2fs",
                    provider.__class__.__name__,
                    elapsed,
                )
                return result
            except Exception as exc:
                last_error = exc
                elapsed = time.perf_counter() - started_at

                if isinstance(provider, GroqProvider):
                    self.governor.mark_groq_rate_limited(exc)

                logger.warning(
                    "Provider %s failed after %.2fs: %s: %s",
                    provider.__class__.__name__,
                    elapsed,
                    type(exc).__name__,
                    exc,
                )

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    def _build_provider_chain(self) -> list:
        preferred = os.getenv("LLM_PROVIDER", "groq").lower()

        if preferred != "groq":
            raise RuntimeError("Only Groq is supported. Set LLM_PROVIDER=groq.")

        providers = []

        try:
            providers.append(GroqProvider())
        except Exception as exc:
            raise RuntimeError(
                "Groq provider could not be initialized. "
                "Set GROQ_API_KEY in Requirement Categorization Feature/.env or in your shell environment."
            ) from exc

        return providers

    def _resolve_model(self, provider, requested_model: str) -> str:
        if isinstance(provider, GroqProvider):
            return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        return requested_model
