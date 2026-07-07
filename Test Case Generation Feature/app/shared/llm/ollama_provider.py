from typing import Optional

from .base_provider import BaseLLMProvider
from .model_config import DEFAULT_MODEL_CONFIG
from app.shared.ollama_client import call_ollama


class OllamaProvider(BaseLLMProvider):

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        num_predict: Optional[int] = None,
    ) -> str:

        config = DEFAULT_MODEL_CONFIG

        return await call_ollama(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            num_predict=num_predict,
            temperature=config.temperature,
            top_p=config.top_p,
            top_k=config.top_k,
            repeat_penalty=config.repeat_penalty
        )
