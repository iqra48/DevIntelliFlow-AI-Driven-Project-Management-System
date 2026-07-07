import asyncio
from typing import Callable, Any


class LLMTimeoutError(Exception):
    pass


class LLMExecutionError(Exception):
    pass


async def execute_with_timeout(
    fn: Callable,
    timeout: float,
    *args,
    **kwargs
) -> Any:

    try:
        return await asyncio.wait_for(
            fn(*args, **kwargs),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise LLMTimeoutError("LLM call exceeded timeout")


async def execute_with_retry(
    fn: Callable,
    retries: int,
    timeout: float,
    *args,
    **kwargs
):

    last_error = None

    for attempt in range(retries + 1):

        try:
            return await execute_with_timeout(
                fn,
                timeout,
                *args,
                **kwargs
            )

        except Exception as e:
            last_error = e

    raise LLMExecutionError(
        f"LLM failed after {retries} retries: {last_error}"
    )
