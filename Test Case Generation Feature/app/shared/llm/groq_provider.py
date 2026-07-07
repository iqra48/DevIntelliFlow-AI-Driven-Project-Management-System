import asyncio
import os
from typing import Optional

from groq import Groq

from .base_provider import BaseLLMProvider


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

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=model or "llama-3.1-8b-instant",
            messages=messages,
            temperature=0,
            max_tokens=num_predict or 512,
            timeout=20,
        )

        return response.choices[0].message.content

    async def health_check(self) -> dict:
        """Lightweight Groq connectivity probe."""
        response = await asyncio.to_thread(self.client.models.list)
        return {
            "provider": "groq",
            "status": "OK",
            "models_visible": len(getattr(response, "data", []) or []),
        }
