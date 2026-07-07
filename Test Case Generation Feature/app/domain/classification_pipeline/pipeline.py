import asyncio

from .steps.input_validation import InputValidationStep
from .steps.semantic_decomposition import SemanticDecompositionStep, SemanticUnit
from .steps.cohesion_verification import SemanticCohesionVerificationStep
from .steps.semantic_classification import SemanticClassificationStep
from .steps.mixed_split import MixedRequirementSplitStep
from .steps.audit_output import AuditOutputAssemblyStep
from .models import ArbitrationResult
from app.shared.structured_logger import ClassificationEventLogger


class ClassificationPipeline:
    def __init__(self):
        self.step_input_validation = InputValidationStep()
        self.step_decomposition = SemanticDecompositionStep()
        self.step_cohesion = SemanticCohesionVerificationStep()
        self.step_classification = SemanticClassificationStep()
        self.step_mixed_split = MixedRequirementSplitStep()
        self.step_audit = AuditOutputAssemblyStep()

    async def run(self, requirement_id: str, text: str, preclassification: dict = None):
        v = self.step_input_validation.execute({"requirement_id": requirement_id, "text": text})
        if v.status == "ABSTAIN":
            ClassificationEventLogger.log_abstention(requirement_id=requirement_id, step="1", reason=v.reason)
            return {"status": "ABSTAIN", "step": "1", "reason": v.reason}

        ClassificationEventLogger.log_input_validation(requirement_id=requirement_id, text_length=len(v.text), status="VALID")

        d = await self.step_decomposition.execute({"requirement_id": requirement_id, "text": v.text})
        if d.status == "ABSTAIN":
            ClassificationEventLogger.log_decomposition(
                requirement_id=requirement_id,
                num_units=1,
                status="FALLBACK",
                reason=d.reason
            )
            semantic_units = [
                SemanticUnit(
                    unit_id=f"{requirement_id}_U1",
                    text=v.text,
                    confidence=0.9
                )
            ]
        else:
            ClassificationEventLogger.log_decomposition(
                requirement_id=requirement_id,
                num_units=len(d.semantic_units),
                status="SUCCESS"
            )
            semantic_units = d.semantic_units

        c = self.step_cohesion.execute(requirement_id, semantic_units)
        if c.status == "ABSTAIN":
            ClassificationEventLogger.log_abstention(requirement_id=requirement_id, step="3", reason=c.reason)
            return {"status": "ABSTAIN", "step": "3", "reason": c.reason}

        ClassificationEventLogger.log_cohesion_verification(requirement_id=requirement_id, status="VALID")
        semantic_units = c.semantic_units

        if preclassification and preclassification.get("type") == "MIXED":
            arbitration = ArbitrationResult(
                requirement_id=requirement_id,
                classification="MIXED",
                basis="Batch semantic classifier"
            )

            classification = "MIXED"

            unit_results = [{
                "behavior_detected": True,
                "quality_detected": True,
                "text": v.text
            }]

            semantic_units = [
                SemanticUnit(
                    unit_id=f"{requirement_id}_U1",
                    text=v.text,
                    confidence=0.95
                )
            ]
        else:
            sem = asyncio.Semaphore(2)

            async def guarded_exec(unit):
                async with sem:
                    return await self.step_classification.execute(requirement_id=unit.unit_id, text=unit.text)

            tasks = [guarded_exec(unit) for unit in semantic_units]
            unit_results = await asyncio.gather(*tasks)

            for result in unit_results:
                if result.status == "ABSTAIN":
                    ClassificationEventLogger.log_abstention(requirement_id=requirement_id, step="4", reason=result.reason)
                    return {"status": "ABSTAIN", "step": "4", "reason": result.reason}

            ClassificationEventLogger.log_unit_classifications(requirement_id=requirement_id, unit_results=unit_results)

            has_behavior = any(r.behavior_detected for r in unit_results)
            has_quality = any(r.quality_detected for r in unit_results)

            if has_behavior and has_quality:
                classification = "MIXED"
            elif has_behavior:
                classification = "FR"
            elif has_quality:
                classification = "NFR"
            else:
                ClassificationEventLogger.log_abstention(requirement_id=requirement_id, step="4", reason="No semantic evidence detected")
                return {"status": "ABSTAIN", "step": "4", "reason": "No semantic evidence detected"}

            ClassificationEventLogger.log_aggregation_decision(
                requirement_id=requirement_id,
                classification=classification,
                has_behavior=has_behavior,
                has_quality=has_quality,
                basis="Deterministic aggregation of unit-level semantic features"
            )

            arbitration = ArbitrationResult(
                requirement_id=requirement_id,
                classification=classification,
                basis="Deterministic aggregation of unit-level semantic features"
            )

        mixed_split = None
        if classification == "MIXED":
            unit_pairs = [
                {
                    "unit_id": unit.unit_id,
                    "text": unit.text,
                    "behavior_detected": result.behavior_detected,
                    "quality_detected": result.quality_detected,
                    "reasoning": result.reasoning
                }
                for unit, result in zip(semantic_units, unit_results)
            ]

            mixed_split = self.step_mixed_split.execute(requirement_id=requirement_id, unit_pairs=unit_pairs)
            if mixed_split.status == "ABSTAIN":
                from app.services.mixed_split_service import split_mixed_requirements

                rewritten = await split_mixed_requirements([v.text])
                entry = rewritten.get(v.text)

                if entry:
                    from .models import SplitRequirement, MixedSplitResult
                    mixed_split = MixedSplitResult(
                        original_id=requirement_id,
                        split=[
                            SplitRequirement(id=f"{requirement_id}_FR", type="FR", text=entry["fr"]),
                            SplitRequirement(id=f"{requirement_id}_NFR", type="NFR", text=entry["nfr"])
                        ]
                    )
                else:
                    ClassificationEventLogger.log_abstention(requirement_id=requirement_id, step="5", reason="Semantic split could not be validated")
                    return {"status": "ABSTAIN", "step": "5", "reason": "Semantic split could not be validated"}

            if mixed_split.split:
                ClassificationEventLogger.log_mixed_split(
                    requirement_id=requirement_id,
                    status="SUCCESS",
                    fr_text=mixed_split.split[0].text,
                    nfr_text=mixed_split.split[1].text
                )

        audit = self.step_audit.execute(semantic_units=semantic_units, arbitration=arbitration, mixed_split=mixed_split)
        ClassificationEventLogger.log_final_classification(
            requirement_id=requirement_id,
            classification=arbitration.classification,
            decision_path=audit.decision_path if audit else [],
            audit_present=True
        )
        return {"status": "SUCCESS", "audit": audit}


Module2Pipeline = ClassificationPipeline
