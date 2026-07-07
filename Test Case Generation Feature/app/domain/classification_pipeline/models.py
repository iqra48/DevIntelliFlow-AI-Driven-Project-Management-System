from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .steps.semantic_classification import SemanticClassificationResult
    from .steps.semantic_decomposition import SemanticUnit


@dataclass
class UnitClassificationPair:
    unit_id: str
    text: str
    behavior_detected: bool
    quality_detected: bool
    reasoning: Optional[str] = None


@dataclass
class ArbitrationResult:
    requirement_id: str
    classification: Optional[str] = None
    basis: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class SplitRequirement:
    id: str
    type: str
    text: str
    quality: Optional[str] = None


@dataclass
class MixedSplitResult:
    original_id: str
    split: Optional[List[SplitRequirement]] = None
    status: Optional[str] = None
    reason: Optional[str] = None
