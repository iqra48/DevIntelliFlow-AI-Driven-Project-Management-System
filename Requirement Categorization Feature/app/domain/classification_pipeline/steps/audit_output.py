from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from ..models import ArbitrationResult, MixedSplitResult
from .semantic_decomposition import SemanticUnit


@dataclass
class AuditOutput:
    requirement_id: str
    final_type: str
    decision_path: List[str]
    semantic_units: List[str]
    derived_requirements: Optional[List[Dict[str, Any]]] = None
    explainability: Optional[str] = None


class AuditOutputAssemblyStep:
    def execute(
        self,
        semantic_units: List[SemanticUnit],
        arbitration: ArbitrationResult,
        mixed_split: Optional[MixedSplitResult] = None
    ) -> AuditOutput:
        decision_path = [
            "input_validation",
            "semantic_decomposition",
            "cohesion_verification",
            "semantic_classification",
            "governed_validation"
        ]

        derived = None
        explanation = arbitration.basis

        if arbitration.classification == "MIXED":
            decision_path.append("mixed_split")

            if mixed_split is None or mixed_split.split is None:
                raise RuntimeError("MIXED classification without split result")

            derived = []
            for r in mixed_split.split:
                entry = {"id": r.id, "type": r.type, "text": r.text}
                if r.quality:
                    entry["quality"] = r.quality
                derived.append(entry)

            explanation = "Behavior and quality constraint detected; requirement split structurally"

        return AuditOutput(
            requirement_id=arbitration.requirement_id,
            final_type=arbitration.classification,
            decision_path=decision_path,
            semantic_units=[u.text for u in semantic_units],
            derived_requirements=derived,
            explainability=explanation
        )
