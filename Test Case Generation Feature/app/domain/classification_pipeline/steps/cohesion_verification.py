from dataclasses import dataclass
from typing import List, Optional

from .semantic_decomposition import SemanticUnit


@dataclass
class CohesionResult:
    requirement_id: str
    semantic_units: Optional[List[SemanticUnit]] = None
    status: Optional[str] = None
    reason: Optional[str] = None


class SemanticCohesionVerificationStep:
    _INSEPARABLE_BUNDLES = [
        {"integrity", "security"},
        {"availability", "reliability"},
        {"performance", "scalability"},
        {"logging", "monitoring"},
        {"privacy", "security"}
    ]

    def execute(self, requirement_id: str, units: List[SemanticUnit]) -> CohesionResult:
        if len(units) <= 1:
            return CohesionResult(requirement_id=requirement_id, semantic_units=units)

        if self._matches_inseparable_bundle(units):
            merged_text = self._merge_units(units)
            return CohesionResult(
                requirement_id=requirement_id,
                semantic_units=[SemanticUnit(unit_id=f"{requirement_id}_U1", text=merged_text, confidence=0.97)]
            )

        if self._has_dependency(units):
            merged_text = self._merge_units(units)
            return CohesionResult(
                requirement_id=requirement_id,
                semantic_units=[SemanticUnit(unit_id=f"{requirement_id}_U1", text=merged_text, confidence=0.96)]
            )

        return CohesionResult(requirement_id=requirement_id, semantic_units=units)

    def _matches_inseparable_bundle(self, units: List[SemanticUnit]) -> bool:
        tokens = set()
        for u in units:
            for word in u.text.lower().split():
                tokens.add(word.strip(",."))
        for bundle in self._INSEPARABLE_BUNDLES:
            if bundle.issubset(tokens):
                return True
        return False

    def _has_dependency(self, units: List[SemanticUnit]) -> bool:
        for u in units:
            if len(u.text.strip().split()) <= 2:
                return True
        return False

    def _merge_units(self, units: List[SemanticUnit]) -> str:
        return " and ".join([u.text.strip() for u in units])
