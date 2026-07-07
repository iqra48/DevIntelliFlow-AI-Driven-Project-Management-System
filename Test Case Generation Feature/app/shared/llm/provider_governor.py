import os
import re
import time
from threading import Lock


def detect_groq_rate_limit_type(message: str) -> str:
    text = message.casefold()
    if "tokens per minute" in text or "tpm" in text:
        return "TPM"
    if "tokens per day" in text or "tpd" in text:
        return "TPD"
    if "requests per minute" in text or "rpm" in text:
        return "RPM"
    if "requests per day" in text or "rpd" in text:
        return "RPD"
    return "unknown"


def parse_retry_after_seconds(message: str) -> float | None:
    match = re.search(r"Please try again in (?:(\d+)m)?([\d.]+)s", message)
    if not match:
        return None
    minutes = int(match.group(1) or 0)
    seconds = float(match.group(2))
    return minutes * 60 + seconds


class ProviderGovernor:
    """Simple in-memory governor for predictive provider routing."""

    def __init__(self):
        self.daily_limit = int(os.getenv("GROQ_DAILY_TOKEN_LIMIT", "100000"))
        self.tokens_used = 0
        self.last_reset = time.time()
        self.groq_blocked_until = 0.0
        self._lock = Lock()

    def estimate_tokens(self, prompt: str, num_predict: int, system_prompt: str | None = None) -> int:
        full_prompt = f"{system_prompt or ''}\n{prompt}".strip()
        prompt_tokens = len(full_prompt.split()) * 1.3
        return int(prompt_tokens + num_predict)

    def can_use_groq(self, estimated_tokens: int) -> tuple[bool, str | None]:
        with self._lock:
            now = time.time()

            if now - self.last_reset > 86400:
                self.tokens_used = 0
                self.last_reset = now
                self.groq_blocked_until = 0.0

            if now < self.groq_blocked_until:
                return False, "Groq is in local cooldown after a rate-limit response"

            if self.tokens_used + estimated_tokens >= self.daily_limit:
                return (
                    False,
                    "Groq local governor cap exceeded: "
                    f"estimated_tokens={estimated_tokens} "
                    f"tokens_used={self.tokens_used} "
                    f"daily_limit={self.daily_limit}",
                )

            return True, None

    def record_groq_usage(self, estimated_tokens: int) -> None:
        with self._lock:
            self.tokens_used += estimated_tokens

    def record_groq_failure(self, error: Exception) -> None:
        message = str(error)

        if "rate_limit_exceeded" not in message or "tokens per day" not in message:
            return

        cooldown_seconds = self._parse_retry_after_seconds(message)

        with self._lock:
            self.tokens_used = self.daily_limit
            self.groq_blocked_until = max(self.groq_blocked_until, time.time() + cooldown_seconds)

    def allow_groq(self, prompt: str, num_predict: int, system_prompt: str | None = None) -> bool:
        estimated = self.estimate_tokens(prompt, num_predict, system_prompt)
        allowed, _ = self.can_use_groq(estimated)
        if allowed:
            self.record_groq_usage(estimated)
        return allowed

    def mark_groq_rate_limited(self, error: Exception) -> None:
        self.record_groq_failure(error)

    def _parse_retry_after_seconds(self, message: str) -> float:
        return parse_retry_after_seconds(message) or 300.0
