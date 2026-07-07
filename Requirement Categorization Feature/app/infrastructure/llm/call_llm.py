import contextvars
import os
import uuid

from .router import LLMRouter
from .retry import execute_with_retry
from app.infrastructure.logging import log_llm_failure
import logging

logger = logging.getLogger(__name__)

_router = None

request_id_ctx = contextvars.ContextVar("request_id", default=None)
request_budget_ctx = contextvars.ContextVar("request_budget", default=None)
request_calls_ctx = contextvars.ContextVar("request_calls", default=0)


def _get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


async def call_llm(
    prompt,
    system_prompt=None,
    model=None,
    num_predict=None
):
    request_id = request_id_ctx.get() or str(uuid.uuid4())
    budget = request_budget_ctx.get()
    calls = request_calls_ctx.get()

    if budget and calls >= budget["max_calls"]:
        lowered_system_prompt = (system_prompt or "").lower()

        if "classification" in lowered_system_prompt:
            return '{"classification":"NFR","behavior_detected":false,"quality_detected":true}'

        if "split" in lowered_system_prompt:
            return '{"splits":{}}'

        if "units" in lowered_system_prompt:
            return '{"decision":"NO_SPLIT"}'

        return '{}'

    request_calls_ctx.set(calls + 1)
    logger.info(
        f"[REQ {request_id}] CALL #{calls + 1} | model={model} | tokens={num_predict}"
    )

    try:
        return await execute_with_retry(
            _get_router().generate,
            retries=1,
            timeout=float(os.getenv("LLM_CALL_TIMEOUT", "60")),
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            num_predict=num_predict
        )
    except Exception as primary_error:
        log_llm_failure(primary_error)

        raise RuntimeError(
            "Groq provider failed during LLM call. "
            f"Error [{type(primary_error).__name__}]: {primary_error}"
        ) from primary_error
