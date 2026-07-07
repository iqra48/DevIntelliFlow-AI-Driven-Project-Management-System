from typing import List
import re


class CapabilityAtomizer:
    """
    Production-grade capability atomizer.

    Converts compound capability phrases into atomic actions.

    Design goals:
    - deterministic
    - no hardcoded domain rules
    - language-agnostic splitting
    - safe for unknown inputs
    """

    SPLIT_PATTERN = re.compile(
        r"\band\b|\bor\b|,|\;|\&",
        flags=re.IGNORECASE
    )

    def atomize(self, capabilities: List[str]) -> List[str]:
        atomic = []

        for cap in capabilities:
            parts = self.SPLIT_PATTERN.split(cap)

            for p in parts:
                p = p.strip()

                if len(p.split()) < 2:
                    continue

                atomic.append(p)

        return atomic
