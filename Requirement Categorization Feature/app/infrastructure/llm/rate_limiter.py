import os
import re
import time
from threading import Lock


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

    def allow_groq(self, prompt: str, num_predict: int, system_prompt: str | None = None) -> bool:
        with self._lock:
            now = time.time()

            if now - self.last_reset > 86400:
                self.tokens_used = 0
                self.last_reset = now
                self.groq_blocked_until = 0.0

            if now < self.groq_blocked_until:
                return False

            estimated = self.estimate_tokens(prompt, num_predict, system_prompt)

            if self.tokens_used + estimated >= self.daily_limit:
                return False

            self.tokens_used += estimated
            return True

    def mark_groq_rate_limited(self, error: Exception) -> None:
        message = str(error)

        if "rate_limit_exceeded" not in message or "tokens per day" not in message:
            return

        cooldown_seconds = self._parse_retry_after_seconds(message)

        with self._lock:
            self.tokens_used = self.daily_limit
            self.groq_blocked_until = max(self.groq_blocked_until, time.time() + cooldown_seconds)

    def _parse_retry_after_seconds(self, message: str) -> float:
        match = re.search(r"Please try again in (\d+)m([\d.]+)s", message)

        if not match:
            return 300.0

        minutes = int(match.group(1))
        seconds = float(match.group(2))
        return minutes * 60 + seconds
