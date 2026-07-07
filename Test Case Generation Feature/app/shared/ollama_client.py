import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11500")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_K_M")
OLLAMA_NUM_THREAD = os.getenv("OLLAMA_NUM_THREAD", None)  # CPU thread count (e.g., "8")
OLLAMA_NUM_PREDICT = os.getenv("OLLAMA_NUM_PREDICT", "256")  # Max tokens to generate (increased for complete requirements)
OLLAMA_NUM_KEEP = os.getenv("OLLAMA_NUM_KEEP", "24")  # Tokens to keep in context
OLLAMA_NUM_CTX = os.getenv("OLLAMA_NUM_CTX", "1200")

# Production timeout config
OLLAMA_TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=1200.0,
    write=600.0,
    pool=600.0
)

# Shared async client (singleton-style)
_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=OLLAMA_BASE,
            timeout=OLLAMA_TIMEOUT,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def call_ollama(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    num_predict: Optional[int] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    repeat_penalty: Optional[float] = None,
) -> str:
    """
    Unified production Ollama client.

    - Uses /api/chat (modern interface)
    - Async
    - Supports system prompt
    - Returns raw string only
    """

    try:
        client = get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        # Build options dict with CPU optimizations
        options = {"temperature": 0}

        if temperature is not None:
            options["temperature"] = float(temperature)

        if top_p is not None:
            options["top_p"] = float(top_p)

        if top_k is not None:
            options["top_k"] = int(top_k)

        if repeat_penalty is not None:
            options["repeat_penalty"] = float(repeat_penalty)
        
        if OLLAMA_NUM_THREAD:
            try:
                options["num_thread"] = int(OLLAMA_NUM_THREAD)
            except ValueError:
                pass

        if OLLAMA_NUM_CTX:
            try:
                options["num_ctx"] = int(OLLAMA_NUM_CTX)
            except ValueError:
                pass
        
        if num_predict is not None:
            options["num_predict"] = int(num_predict)
        elif OLLAMA_NUM_PREDICT:
            try:
                options["num_predict"] = int(OLLAMA_NUM_PREDICT)
            except ValueError:
                pass
        
        if OLLAMA_NUM_KEEP:
            try:
                options["num_keep"] = int(OLLAMA_NUM_KEEP)
            except ValueError:
                pass

        response = await client.post(
            "/api/chat",
            json={
                "model": model or OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": options,
            },
        )

        response.raise_for_status()
        data = response.json()

        result = (
            data.get("response")
            or data.get("message", {}).get("content")
            or ""
        ).strip()
        
        logger.debug(f"Ollama full response: {data}")
        logger.debug(f"Extracted content: {result[:100]}")
        
        return result

    except Exception as e:
        logger.exception("Ollama call failed")
        raise


async def shutdown_ollama():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def warmup(model: Optional[str] = None) -> float:
    """Call Ollama with a tiny prompt to warm up model and connection.

    Returns the elapsed seconds for the warmup call.
    """
    import time

    start = time.perf_counter()
    try:
        # very small prompt to initialize model/context
        await call_ollama(
            prompt="Hi",
            model=model or OLLAMA_MODEL,
            num_predict=1
        )
    except Exception:
        # Do not fail startup on warmup errors; caller can decide
        logger.debug("Ollama warmup failed, continuing")
    elapsed = time.perf_counter() - start
    logger.info(f"Ollama warmup completed in {elapsed:.2f}s")
    return elapsed
