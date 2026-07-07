from dataclasses import dataclass
from typing import Optional

from app.infrastructure.llm.call_llm import call_llm
from app.infrastructure.llm.output_validation import guarded_llm_call


@dataclass
class SemanticClassificationResult:
    requirement_id: str
    classification: Optional[str]
    behavior_detected: bool
    quality_detected: bool
    reasoning: Optional[str]
    status: Optional[str] = None
    reason: Optional[str] = None


class SemanticClassificationStep:
    async def execute(self, requirement_id: str, text: str) -> SemanticClassificationResult:
        system_prompt = """
You are a requirements classification engine.

Definitions:
- FR (Functional Requirement): Describes a system BEHAVIOR or CAPABILITY - what the system DOES/PERFORMS.
- NFR (Non-Functional Requirement): Describes a QUALITY CONSTRAINT or property - how well/fast/secure it performs.
- MIXED: Contains BOTH a behavior (what it does) AND a quality constraint (how it does it).

Always extract:
{
  "classification": "FR | NFR | MIXED",
  "behavior_detected": true/false,
  "quality_detected": true/false,
  "reasoning": "brief explanation"
}
"""
        user_prompt = f"""
Requirement:
{text}
"""
        try:
            data = await guarded_llm_call(
                lambda prompt, system: call_llm(
                    prompt=prompt,
                    system_prompt=system,
                    num_predict=80
                ),
                user_prompt,
                system_prompt,
                {
                    "classification": {"FR", "NFR", "MIXED"},
                    "behavior_detected": {True, False},
                    "quality_detected": {True, False}
                }
            )
            classification = data.get("classification")
            behavior = data.get("behavior_detected")
            quality = data.get("quality_detected")
            reasoning = data.get("reasoning")

            if classification == "FR" and not behavior:
                raise ValueError("FR without behavior")
            if classification == "NFR" and not quality:
                raise ValueError("NFR without quality")
            if classification == "MIXED" and not (behavior and quality):
                raise ValueError("MIXED without both features")

            return SemanticClassificationResult(
                requirement_id=requirement_id,
                classification=classification,
                behavior_detected=behavior,
                quality_detected=quality,
                reasoning=reasoning
            )
        except Exception as e:
            return SemanticClassificationResult(
                requirement_id=requirement_id,
                classification=None,
                behavior_detected=False,
                quality_detected=False,
                reasoning=None,
                status="ABSTAIN",
                reason=str(e)
            )
