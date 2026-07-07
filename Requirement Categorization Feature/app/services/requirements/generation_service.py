from typing import List
import logging
from app.services.requirements.input_segmentation import InputSegmentationService
from app.services.requirements.req_generator import (
    generate_numbered_requirements_async,
    calculate_generation_tokens,
)
from app.services.requirements.req_extractor import extract_numbered_requirements

logger = logging.getLogger(__name__)
SEGMENT_THRESHOLD = 900


async def generate_requirements(text: str) -> List[str]:
    """
    Service wrapper for requirement generation.

    - Calls LLM generator
    - Extracts numbered requirements deterministically
    - Returns clean list of requirement strings
    """

    token_budget = calculate_generation_tokens(text)

    if token_budget <= SEGMENT_THRESHOLD:
        raw = await generate_numbered_requirements_async(text)
        return extract_numbered_requirements(raw)

    segmentation = InputSegmentationService()
    segments = segmentation.segment(text)
    logger.info("Segmentation triggered: %d segments", len(segments))

    all_requirements = []

    for segment in segments:
        raw = await generate_numbered_requirements_async(segment)
        extracted = extract_numbered_requirements(raw)
        all_requirements.extend(extracted)

    unique = []
    seen = set()

    for r in all_requirements:
        norm = " ".join(r.lower().split())

        if norm not in seen:
            seen.add(norm)
            unique.append(r)

    return unique
