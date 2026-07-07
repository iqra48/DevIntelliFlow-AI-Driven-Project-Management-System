from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    """
    Immutable configuration for deterministic LLM inference.
    """

    model: str
    temperature: float
    top_p: float
    top_k: int
    repeat_penalty: float
    num_ctx: int
    num_predict: int


# Production deterministic configuration
DEFAULT_MODEL_CONFIG = ModelConfig(
    model="llama-3.1-8b-instant",
    temperature=0.0,
    top_p=1.0,
    top_k=0,
    repeat_penalty=1.0,
    num_ctx=4096,
    num_predict=512
)
