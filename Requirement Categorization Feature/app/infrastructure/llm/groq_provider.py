import asyncio
import logging
import os
from typing import Optional

from groq import Groq

from .base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


def _is_rate_limit_error(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    message = str(error).lower()
    return status_code == 429 or "rate_limit" in message or "rate limit" in message


class GroqProvider(BaseLLMProvider):

    def __init__(self):

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError("GROQ_API_KEY not configured")

        self.client = Groq(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        num_predict: Optional[int] = None,
    ) -> str:

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        max_retries = int(os.getenv("GROQ_RATE_LIMIT_MAX_RETRIES", "3"))
        base_delay = float(os.getenv("GROQ_RATE_LIMIT_BASE_DELAY", "1.5"))
        timeout = float(os.getenv("GROQ_REQUEST_TIMEOUT", "45"))
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=model or "llama-3.3-70b-versatile",
                    messages=messages,
                    temperature=0,
                    max_tokens=num_predict or 512,
                    timeout=timeout,
                )
                return response.choices[0].message.content
            except Exception as exc:
                last_error = exc
                if not _is_rate_limit_error(exc) or attempt >= max_retries:
                    raise

                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "GROQ_RATE_LIMIT_RETRY | attempt=%s | max_retries=%s | "
                    "sleep_seconds=%.2f",
                    attempt + 1,
                    max_retries,
                    delay,
                )
                await asyncio.sleep(delay)

        raise last_error

    async def health_check(self) -> dict:
        """Lightweight Groq connectivity probe."""
        response = await asyncio.to_thread(self.client.models.list)
        return {
            "provider": "groq",
            "status": "OK",
            "models_visible": len(getattr(response, "data", []) or []),
        }
