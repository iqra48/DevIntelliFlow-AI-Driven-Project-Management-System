import asyncio
import logging
import time
from typing import Dict

from app.domain import ClassificationPipeline
from app.services.requirements.batch_classifier import classify_requirements_batch
from app.services.requirements.generation_service import generate_requirements
from app.services.requirements.semantic_deduplicator import SemanticDeduplicator

logger = logging.getLogger(__name__)
MAX_LOW_ESCALATIONS = 2


class RequirementEngine:
    """
    Production-grade orchestration layer.

    Responsible for:
    - Coordinating generation (user input -> atomic IEEE requirements)
    - Batch classifying (FR/NFR/MIXED in 1 LLM call)
    - Returning structured output

    Note: Generation now produces IEEE-formatted output directly.
    Rewrite stage has been merged into generation for efficiency.
    """

    def __init__(self):
        self.classification_pipeline = ClassificationPipeline()
        self.semantic_deduplicator = SemanticDeduplicator()

    async def process(self, text: str) -> Dict:
        """
        Main processing pipeline: Generate (IEEE-formatted) -> Batch Classify -> Auto-split MIXED

        Step 3 enhancement: MIXED classifications are automatically split into separate FR + NFR
        requirements. Final output contains only FR and NFR types (industry standard).
        """
        total_started = time.perf_counter()

        generator_input = text

        started = time.perf_counter()
        generated = await generate_requirements(generator_input)
        logger.info("Pipeline stage=generate elapsed=%.2fs count=%s", time.perf_counter() - started, len(generated))

        deduped = []
        seen = set()

        for r in generated:
            norm = " ".join(r.lower().split())
            if norm not in seen:
                seen.add(norm)
                deduped.append(r)

        generated = deduped

        started = time.perf_counter()
        batch_results = await classify_requirements_batch(generated)
        logger.info("Pipeline stage=batch_classify elapsed=%.2fs count=%s", time.perf_counter() - started, len(batch_results))

        tasks = []
        mixed_requirements = []
        mixed_index_map = {}
        low_escalation_count = 0

        for idx, req_text in enumerate(generated, 1):
            classification = batch_results.get(req_text, {}).get("type", "FR")
            confidence = batch_results.get(req_text, {}).get("confidence", "HIGH")

            if classification == "MIXED":
                mixed_requirements.append(req_text)
                mixed_index_map[req_text] = idx
                tasks.append(None)

            elif confidence == "LOW":
                if low_escalation_count < MAX_LOW_ESCALATIONS:
                    low_escalation_count += 1
                    tasks.append(
                        self.classification_pipeline.run(
                            requirement_id=f"REQ_{idx}",
                            text=req_text,
                            preclassification=batch_results.get(req_text)
                        )
                    )
                else:
                    tasks.append({
                        "status": "SUCCESS",
                        "audit": {
                            "requirement_id": f"REQ_{idx}",
                            "final_type": classification,
                            "derived_requirements": None,
                            "note": "ESCALATION_SKIPPED_DUE_TO_BUDGET"
                        }
                    })
            else:
                tasks.append({
                    "status": "SUCCESS",
                    "audit": {
                        "requirement_id": f"REQ_{idx}",
                        "final_type": classification,
                        "derived_requirements": None
                    }
                })

        if mixed_requirements:
            from app.services.requirements.mixed_split_service import split_mixed_requirements

            started = time.perf_counter()
            split_results = await split_mixed_requirements(mixed_requirements)
            logger.info("Pipeline stage=mixed_split elapsed=%.2fs count=%s", time.perf_counter() - started, len(mixed_requirements))

            for req_text in mixed_requirements:
                idx = mixed_index_map[req_text]
                tasks[idx - 1] = split_results

        pipeline_results = await asyncio.gather(*[
            t if asyncio.iscoroutine(t) else asyncio.sleep(0, result=t)
            for t in tasks
        ])

        results = []
        seen_requirements = set()

        def _normalize(text: str) -> str:
            return " ".join(text.lower().split())

        for idx, result in enumerate(pipeline_results, 1):
            req_text = generated[idx - 1]

            if isinstance(result, dict) and req_text in result:
                split = result[req_text]

                fr = split["fr"]
                nfr = split.get("nfr", "")

                for text, rtype in [(fr, "FR"), (nfr, "NFR")]:
                    if not text:
                        continue
                    norm = _normalize(text)
                    if norm in seen_requirements:
                        continue

                    seen_requirements.add(norm)

                    results.append({
                        "id": f"REQ_{idx}_{rtype}",
                        "requirement": text,
                        "classification_type": rtype,
                        "classification": {
                            "status": "SUCCESS",
                            "type": rtype
                        }
                    })

                continue

            if result["status"] != "SUCCESS":
                results.append({
                    "id": f"REQ_{idx}",
                    "requirement": req_text,
                    "classification_type": "ABSTAIN",
                    "classification": {
                        "status": "ABSTAIN",
                        "reason": result.get("reason")
                    }
                })
                continue

            audit = result["audit"]

            if isinstance(audit, dict):
                final_type = audit.get("final_type")
                derived_requirements = audit.get("derived_requirements")
                requirement_id = audit.get("requirement_id")
            else:
                final_type = audit.final_type
                derived_requirements = audit.derived_requirements
                requirement_id = audit.requirement_id

            if final_type == "MIXED" and derived_requirements:
                for derived in derived_requirements:
                    text = derived["text"]
                    norm = _normalize(text)

                    if norm in seen_requirements:
                        continue

                    seen_requirements.add(norm)

                    results.append({
                        "id": derived["id"],
                        "requirement": text,
                        "classification_type": derived["type"],
                        "classification": {
                            "status": "SUCCESS",
                            "type": derived["type"]
                        }
                    })
            else:
                norm = _normalize(req_text)

                if norm not in seen_requirements:
                    seen_requirements.add(norm)
                    results.append({
                        "id": requirement_id,
                        "requirement": req_text,
                        "classification_type": final_type,
                        "classification": {
                            "status": "SUCCESS",
                            "type": final_type
                        }
                    })

        started = time.perf_counter()
        final_texts = [r["requirement"] for r in results]
        deduped_texts = set(self.semantic_deduplicator.deduplicate(final_texts))

        final_results = []
        seen = set()

        for r in results:
            norm = " ".join(r["requirement"].lower().split())
            if r["requirement"] in deduped_texts and norm not in seen:
                seen.add(norm)
                final_results.append(r)

        results = final_results
        logger.info("Pipeline stage=semantic_deduplicate_final elapsed=%.2fs count=%s", time.perf_counter() - started, len(results))

        logger.info("Pipeline stage=complete elapsed=%.2fs", time.perf_counter() - total_started)
        return {
            "status": "SUCCESS",
            "results": results
        }
