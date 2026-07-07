from typing import List, Dict, Any

from ..models import SplitRequirement, MixedSplitResult


class MixedRequirementSplitStep:
    def execute(self, requirement_id: str, unit_pairs: List[Dict[str, Any]]) -> MixedSplitResult:
        if not unit_pairs:
            return MixedSplitResult(
                original_id=requirement_id,
                status="ABSTAIN",
                reason="No semantic units provided for MIXED split"
            )

        fr_units = []
        nfr_units = []

        for pair in unit_pairs:
            behavior = pair.get("behavior_detected", False)
            quality = pair.get("quality_detected", False)
            text = pair.get("text", "")

            if behavior and not quality:
                fr_units.append(text)
            elif quality and not behavior:
                nfr_units.append(text)

        for pair in unit_pairs:
            if pair.get("behavior_detected") and pair.get("quality_detected"):
                return MixedSplitResult(
                    original_id=requirement_id,
                    status="ABSTAIN",
                    reason="Unit contains inseparable behavior + quality"
                )

        if not fr_units or not nfr_units:
            return MixedSplitResult(
                original_id=requirement_id,
                status="ABSTAIN",
                reason="Cannot create semantically pure FR/NFR split"
            )

        return MixedSplitResult(
            original_id=requirement_id,
            split=[
                SplitRequirement(id=f"{requirement_id}_FR", type="FR", text=" and ".join(fr_units)),
                SplitRequirement(id=f"{requirement_id}_NFR", type="NFR", text=" and ".join(nfr_units))
            ]
        )
