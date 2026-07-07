from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMProvider(ABC):
    """
    Production-grade provider interface.

    All LLM providers must implement this interface.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        num_predict: Optional[int] = None,
    ) -> str:
        pass
