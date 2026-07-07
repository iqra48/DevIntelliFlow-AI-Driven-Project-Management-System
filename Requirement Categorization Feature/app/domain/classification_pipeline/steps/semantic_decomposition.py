from dataclasses import dataclass
from typing import List, Dict, Optional

from app.infrastructure.llm.call_llm import call_llm, request_budget_ctx, request_calls_ctx
from app.infrastructure.llm.output_validation import OutputValidationError, guarded_llm_call


@dataclass
class SemanticUnit:
    unit_id: str
    text: str
    confidence: float


@dataclass
class DecompositionResult:
    requirement_id: str
    semantic_units: Optional[List[SemanticUnit]] = None
    status: Optional[str] = None
    reason: Optional[str] = None


class SemanticDecompositionStep:
    async def execute(self, validated_input: Dict) -> DecompositionResult:
        req_id = validated_input["requirement_id"]
        text = validated_input["text"]
        llm_units = await self._llm_propose_units(text)

        if llm_units is None:
            return DecompositionResult(
                requirement_id=req_id,
                semantic_units=[SemanticUnit(unit_id=f"{req_id}_U1", text=text, confidence=0.95)]
            )

        if not self._is_valid_split(llm_units, text):
            fallback_units = self._rule_based_split(text)
            if fallback_units and self._is_valid_split(fallback_units, text):
                llm_units = fallback_units
            else:
                return DecompositionResult(requirement_id=req_id, status="ABSTAIN", reason="No safe semantic split available")

        units = [
            SemanticUnit(unit_id=f"{req_id}_U{idx}", text=unit_text.strip(), confidence=0.95)
            for idx, unit_text in enumerate(llm_units, start=1)
        ]
        return DecompositionResult(requirement_id=req_id, semantic_units=units)

    async def _llm_propose_units(self, text: str) -> Optional[List[str]]:
        calls = request_calls_ctx.get()
        budget = request_budget_ctx.get()

        if budget and calls > budget["max_calls"] * 0.7:
            return None

        system_prompt = (
            "You are a semantic analysis assistant.\n"
            "Identify independent testable intents.\n"
            "Do not rewrite or infer.\n"
            "Return JSON only.\n"
            "If unsure, return exactly:\n"
            '{ "decision": "NO_SPLIT" }'
        )
        user_prompt = f"""
Requirement:
\"{text}\"

Return one of the following exactly:

1.
{{ \"units\": [\"unit 1\", \"unit 2\"] }}

OR

2.
{{ \"decision\": \"NO_SPLIT\" }}
"""
        try:
            data = await guarded_llm_call(
                lambda prompt, system: call_llm(prompt=prompt, system_prompt=system),
                user_prompt,
                system_prompt,
                {}
            )
        except OutputValidationError:
            return None

        if data.get("decision") == "NO_SPLIT":
            return None
        units = data.get("units")
        if not isinstance(units, list):
            return None
        cleaned = [u.strip() for u in units if isinstance(u, str)]
        return cleaned if len(cleaned) >= 2 else None

    def _is_valid_split(self, units: List[str], original_text: str) -> bool:
        original_lower = original_text.lower()
        for u in units:
            if u.lower() not in original_lower:
                return False
        if any(len(u.split()) < 3 for u in units):
            return False
        subjects = set()
        for u in units:
            ul = u.lower()
            if "user" in ul:
                subjects.add("user")
            if "system" in ul or "application" in ul:
                subjects.add("system")
        if len(subjects) >= 2:
            return True
        return True

    def _rule_based_split(self, text: str) -> Optional[List[str]]:
        lowered = text.lower()
        if " and " not in lowered:
            return None
        parts = text.split(" and ")
        if len(parts) != 2:
            return None
        left, right = parts[0].strip(), parts[1].strip()
        if len(left.split()) < 3 or len(right.split()) < 3:
            return None
        return [left, right]
