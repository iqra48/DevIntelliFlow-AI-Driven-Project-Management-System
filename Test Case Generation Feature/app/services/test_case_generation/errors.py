from app.shared.llm.exceptions import GroqGovernorLimitExceeded
from app.shared.llm.provider_governor import detect_groq_rate_limit_type


def is_rate_limit_error(exc: Exception) -> bool:
    """
    Detect provider/rate-limit/quota errors defensively.
    """
    if not isinstance(exc, Exception):
        return False

    if isinstance(exc, GroqGovernorLimitExceeded):
        return True

    if getattr(exc, "status_code", None) == 429:
        return True

    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 429:
        return True

    if getattr(exc, "code", None) == 429:
        return True

    class_name = type(exc).__name__
    if "RateLimit" in class_name or "RateLimitError" in class_name:
        return True

    message = str(exc).casefold()
    return any(
        term in message
        for term in ("rate limit", "ratelimit", "too many requests", "429", "quota")
    )


def provider_status_from_exception(exc: Exception) -> str:
    """
    Map provider exceptions to public test case generation statuses.
    """
    return "RATE_LIMITED" if is_rate_limit_error(exc) else "PROVIDER_FAILED"


def rate_limit_type_from_exception(exc: Exception) -> str | None:
    if not is_rate_limit_error(exc):
        return None
    return detect_groq_rate_limit_type(str(exc))
