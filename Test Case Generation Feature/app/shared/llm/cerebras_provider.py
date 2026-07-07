import os
from typing import Optional

import httpx

from .base_provider import BaseLLMProvider


class CerebrasProvider(BaseLLMProvider):
    DEFAULT_MODEL = "gpt-oss-120b"
    DEFAULT_BASE_URL = "https://api.cerebras.ai/v1"

    def __init__(self):
        self.api_key = os.getenv("CEREBRAS_API_KEY")
        if not self.api_key:
            raise RuntimeError("CEREBRAS_API_KEY not configured")
        self.base_url = os.getenv("CEREBRAS_BASE_URL", self.DEFAULT_BASE_URL).rstrip("/")

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

        payload = {
            "model": model or os.getenv("CEREBRAS_MODEL", self.DEFAULT_MODEL),
            "messages": messages,
            "temperature": 0.0,
        }
        if num_predict is not None:
            min_tokens = int(os.getenv("CEREBRAS_MIN_OUTPUT_TOKENS", "2048"))
            payload["max_completion_tokens"] = max(num_predict, min_tokens)

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Cerebras response missing assistant content") from exc

        if not isinstance(content, str) or not content:
            raise RuntimeError("Cerebras response missing assistant content")
        return content

    async def health_check(self) -> dict:
        model = os.getenv("CEREBRAS_MODEL", self.DEFAULT_MODEL)
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            data = response.json()
        models = data.get("data", []) if isinstance(data, dict) else []
        return {
            "provider": "cerebras",
            "status": "OK",
            "model": model,
            "models_visible": len(models) if isinstance(models, list) else None,
        }
