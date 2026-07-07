from typing import List
import re


class AtomicIntentEnforcer:
    """
    Ensures each semantic intent contains exactly one action.

    Deterministic enforcement stage before requirement generation.
    """

    ACTION_SPLIT_PATTERN = re.compile(
        r"\band\b|\bor\b|,|\;|\&",
        flags=re.IGNORECASE
    )

    def enforce(self, intents: List[str]) -> List[str]:

        atomic = []

        for intent in intents:

            parts = self.ACTION_SPLIT_PATTERN.split(intent)

            for p in parts:

                cleaned = p.strip()

                # discard only trivial tokens
                if len(cleaned.split()) < 2:
                    continue

                atomic.append(cleaned)

        return atomic
