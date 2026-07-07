from dataclasses import dataclass
from typing import Dict, Optional
import regex as re


@dataclass
class ValidationResult:
    requirement_id: str
    status: str
    text: Optional[str] = None
    reason: Optional[str] = None


class InputValidationStep:
    _MULTI_SENTENCE_PATTERN = re.compile(r"[.;]\s+")
    _NON_TEXT_PATTERN = re.compile(r"^[\W_]+$")
    _META_PATTERNS = [
        r"\bbest practice\b",
        r"\bimportant\b",
        r"\bshould consider\b",
        r"\bguideline\b",
        r"\bdesign should\b"
    ]

    def execute(self, requirement: Dict) -> ValidationResult:
        req_id = requirement.get("requirement_id", "UNKNOWN")
        raw_text = requirement.get("text", "")
        text = raw_text.strip()

        if not text or len(text.split()) < 3:
            return ValidationResult(requirement_id=req_id, status="ABSTAIN", reason="Empty or trivial requirement")

        if self._NON_TEXT_PATTERN.match(text):
            return ValidationResult(requirement_id=req_id, status="ABSTAIN", reason="Non-linguistic content")

        if self._MULTI_SENTENCE_PATTERN.search(text):
            return ValidationResult(requirement_id=req_id, status="ABSTAIN", reason="Multiple sentences detected - re-route to Module 1")

        lowered = text.lower()
        for pattern in self._META_PATTERNS:
            if re.search(pattern, lowered):
                return ValidationResult(requirement_id=req_id, status="ABSTAIN", reason="Non-testable META requirement")

        return ValidationResult(requirement_id=req_id, status="VALID", text=text)
