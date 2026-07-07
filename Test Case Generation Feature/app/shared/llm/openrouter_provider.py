import asyncio
import os
from typing import Optional

from .base_provider import BaseLLMProvider


class OpenRouterProvider(BaseLLMProvider):
    DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct"

    def __init__(self):
        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not configured")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package not installed for OpenRouterProvider") from exc

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

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

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=model or self.DEFAULT_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=num_predict or 512,
            timeout=20,
        )

        return response.choices[0].message.content
