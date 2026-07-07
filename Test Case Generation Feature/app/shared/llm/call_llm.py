import contextvars
import os
import uuid

from .llm_router import LLMRouter, is_strict_groq_mode
from .provider_metadata import request_provider_metadata_ctx
from .resilient_executor import execute_with_retry
from app.shared.structured_logger import log_llm_failure
import logging

logger = logging.getLogger(__name__)

_router = None

request_id_ctx = contextvars.ContextVar("request_id", default=None)
request_budget_ctx = contextvars.ContextVar("request_budget", default=None)
request_calls_ctx = contextvars.ContextVar("request_calls", default=0)


def llm_call_timeout_seconds() -> float:
    try:
        value = float(os.getenv("LLM_CALL_TIMEOUT_SECONDS", "120") or "120")
    except ValueError:
        return 120.0
    return value if value >= 1 else 120.0


def _new_provider_metadata() -> dict:
    return {
        "primary_provider": None,
        "strict_provider": None,
        "provider_used_by_stage": {},
        "provider_role_map": {},
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


def _get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


async def call_llm(
    prompt,
    system_prompt=None,
    model=None,
    num_predict=None,
    stage=None,
):
    request_id = request_id_ctx.get() or str(uuid.uuid4())
    budget = request_budget_ctx.get()
    calls = request_calls_ctx.get()

    if budget and calls >= budget["max_calls"]:
        lowered_system_prompt = (system_prompt or "").casefold()

        if "classification" in lowered_system_prompt:
            return '{"classification":"NFR","behavior_detected":false,"quality_detected":true}'

        if "split" in lowered_system_prompt:
            return '{"splits":{}}'

        if "units" in lowered_system_prompt:
            return '{"decision":"NO_SPLIT"}'

        return '{}'

    request_calls_ctx.set(calls + 1)
    if request_provider_metadata_ctx.get() is None:
        request_provider_metadata_ctx.set(_new_provider_metadata())
    logger.info(
        f"[REQ {request_id}] CALL #{calls + 1} | model={model} | tokens={num_predict}"
    )

    def record_provider_metadata(metadata: dict) -> None:
        current = request_provider_metadata_ctx.get()
        if current is None:
            current = _new_provider_metadata()
            request_provider_metadata_ctx.set(current)

        if metadata.get("primary_provider") is not None:
            current["primary_provider"] = metadata.get("primary_provider")
        if metadata.get("strict_provider") is not None:
            current["strict_provider"] = metadata.get("strict_provider")
        for stage_name, provider_name in (
            metadata.get("provider_used_by_stage") or {}
        ).items():
            current["provider_used_by_stage"][stage_name] = provider_name
        for stage_name, provider_name in (metadata.get("provider_role_map") or {}).items():
            current["provider_role_map"][stage_name] = provider_name
        if metadata.get("fallback_used"):
            current["fallback_used"] = True
            current["fallback_provider"] = metadata.get("fallback_provider")
            current["fallback_reason"] = metadata.get("fallback_reason")
        if metadata.get("rate_limit_stage"):
            current["rate_limit_stage"] = metadata.get("rate_limit_stage")
            current["rate_limit_type"] = metadata.get("rate_limit_type") or "unknown"
        current["retry_attempts"] = current.get("retry_attempts", 0) + int(
            metadata.get("retry_attempts") or 0
        )
        current["provider_wait_seconds_total"] = float(
            current.get("provider_wait_seconds_total") or 0.0
        ) + float(metadata.get("provider_wait_seconds_total") or 0.0)
        for stage_name, wait_seconds in (
            metadata.get("provider_wait_by_stage") or {}
        ).items():
            current["provider_wait_by_stage"][stage_name] = float(
                current["provider_wait_by_stage"].get(stage_name) or 0.0
            ) + float(wait_seconds or 0.0)
        for provider_name, wait_seconds in (
            metadata.get("provider_wait_by_provider") or {}
        ).items():
            current["provider_wait_by_provider"][provider_name] = float(
                current["provider_wait_by_provider"].get(provider_name) or 0.0
            ) + float(wait_seconds or 0.0)

    try:
        if is_strict_groq_mode():
            return await _get_router().generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                num_predict=num_predict,
                stage=stage,
                metadata_recorder=record_provider_metadata,
            )

        return await execute_with_retry(
            _get_router().generate,
            retries=0,
            timeout=llm_call_timeout_seconds(),
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            num_predict=num_predict,
            stage=stage,
            metadata_recorder=record_provider_metadata,
        )
    except Exception as primary_error:
        log_llm_failure(primary_error)
        raise
