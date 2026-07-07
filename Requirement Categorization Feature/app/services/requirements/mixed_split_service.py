"""
Mixed Requirement Split Service

Splits MIXED requirements (containing both a system behavior and a quality
constraint) into a separate FR and NFR pair using a single LLM call.

Design constraints
------------------
- Both FR and NFR outputs must begin with "The system shall" so they pass
  the IEEE sentence filter in req_extractor.py without modification.
  The old pattern ("User authentication shall be secure.") uses a passive
  noun subject that the extractor rejects, causing the NFR to silently
  disappear and a phantom duplicate FR to appear in the final output.

- The system prompt uses structural templates, not keyword lists.
  A list of banned verbs ("authenticate, process, send...") is hardcoded
  and breaks on any verb outside the list.  The structural templates
  show the model the SHAPE of the output, not a vocabulary constraint.

- Large batches are chunked identically to batch_classifier to prevent
  prompt overflow on free-tier APIs.
"""

import logging
from typing import Dict, List

from app.infrastructure.llm.call_llm import call_llm
from app.infrastructure.llm.output_validation import OutputValidationError, guarded_llm_call
from app.infrastructure.logging import ClassificationEventLogger

logger = logging.getLogger(__name__)

_MAX_BATCH_SIZE = 10  # Splits are larger than classifications; smaller chunks

# â”€â”€ Prompt â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#
# Why both outputs use "The system shall"
# ----------------------------------------
# The downstream req_extractor.py enforces IEEE format: every requirement
# must begin with "The system shall".  If the NFR uses a passive subject
# ("Payment processing shall be secure."), the extractor silently drops it.
# The caller in requirement_engine.py has no way to detect this drop, so it
# emits only the FR â€” creating a phantom duplicate of the original MIXED
# requirement stripped of its quality constraint.
#
# The correct NFR form in IEEE style is:
#   "The system shall [verb] [object] [measurable quality property]."
# where the quality property makes it an NFR (it measures a system attribute),
# but the sentence structure keeps it IEEE-compatible.
#
# Examples of the correct transformation:
#   MIXED:  "The system shall process payments securely."
#   FR:     "The system shall process payments."
#   NFR:    "The system shall ensure that payment processing meets security standards."
#
#   MIXED:  "The system shall confirm successful transactions immediately."
#   FR:     "The system shall confirm successful transactions."
#   NFR:    "The system shall confirm successful transactions within an acceptable response time."
#
#   MIXED:  "The system shall encrypt customer data during storage and transmission."
#   FR:     "The system shall encrypt customer data."
#   NFR:    "The system shall encrypt customer data using industry-standard methods for storage and transmission."
#
# The NFR carries the quality scope; the FR carries the pure behavior.
# Neither is a passive noun-subject sentence.

_SYSTEM_PROMPT = """\
You are a requirements engineer splitting MIXED requirements into FR and NFR pairs.

A MIXED requirement contains both a system behavior (what the system does) and
a quality constraint (how well, how fast, or by what method it does it).

YOUR TASK
For each input, produce one FR and one NFR that together preserve all information
from the original.

FR RULE
- Describes the system behavior only.
- Must begin with: The system shall
- Must contain an active verb and its direct object.
- Must NOT include quality modifiers (adverbs, time bounds, method phrases).

NFR RULE
- Describes the quality property or constraint only.
- Must begin with: The system shall
- Must be written as a measurable system property, not a passive noun phrase.
- Must preserve the quality scope from the original (the adverb, time bound, or method).

TRANSFORMATION PATTERN
  MIXED:  "The system shall [verb] [object] [quality]."
  FR:     "The system shall [verb] [object]."
  NFR:    "The system shall ensure that [object] [verb past-tense or noun] [quality]."
       OR "The system shall [verb] [object] [expanded quality property]."

EXAMPLES
  MIXED:  "The system shall process payments securely."
  FR:     "The system shall process payments."
  NFR:    "The system shall ensure that payment processing meets security requirements."

  MIXED:  "The system shall confirm successful transactions immediately."
  FR:     "The system shall confirm successful transactions."
  NFR:    "The system shall confirm successful transactions within an acceptable response time."

  MIXED:  "The system shall encrypt customer data during storage and transmission."
  FR:     "The system shall encrypt customer data."
  NFR:    "The system shall encrypt customer data using industry-standard methods during storage and transmission."

  MIXED:  "The system shall store user credentials securely."
  FR:     "The system shall store user credentials."
  NFR:    "The system shall ensure that user credential storage meets security standards."

  MIXED:  "The system shall load the product catalog quickly."
  FR:     "The system shall load the product catalog."
  NFR:    "The system shall load the product catalog within an acceptable response time."

OUTPUT
Return ONLY valid JSON.  No markdown, no explanation.
{"splits":{"1":{"fr":"...","nfr":"..."},"2":{"fr":"...","nfr":"..."}}}\
"""

_USER_PROMPT_TEMPLATE = """\
Split each MIXED requirement below.

{numbered_list}

Return ONLY:
{{"splits":{{"1":{{"fr":"...","nfr":"..."}}}}}}"""


# â”€â”€ Token budget â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _output_token_budget(count: int) -> int:
    """
    Each split produces two IEEE sentences â‰ˆ 40 tokens each = ~80 tokens per item.
    1.4x safety margin.  Hard bounds prevent waste and truncation.
    """
    tokens = int(count * 80 * 1.4)
    return max(160, min(1024, tokens))


# â”€â”€ Chunking â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _chunk(items: List[str], size: int) -> List[List[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


# â”€â”€ Core LLM call â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _split_chunk(requirements: List[str]) -> Dict[str, Dict[str, str]]:
    """
    Split one chunk of MIXED requirements.

    Returns a dict mapping 1-based string index â†’ {"fr": ..., "nfr": ...}.
    Raises on parse failure.
    """
    numbered = "\n".join(f"{i+1}. {r}" for i, r in enumerate(requirements))
    user_prompt = _USER_PROMPT_TEMPLATE.format(numbered_list=numbered)
    token_budget = _output_token_budget(len(requirements))

    data = await guarded_llm_call(
        lambda prompt, system: call_llm(
            prompt=prompt,
            system_prompt=system,
            num_predict=token_budget,
        ),
        user_prompt,
        _SYSTEM_PROMPT,
        {},
    )

    splits = data.get("splits", {})
    if not isinstance(splits, dict):
        raise OutputValidationError("Missing or invalid 'splits' object in response")

    return splits


def _is_valid_ieee(text: str) -> bool:
    """
    Verify the output passes the same IEEE filter as req_extractor.py.
    Prevents silently dropping an NFR that doesn't start with "The system shall".
    """
    tokens = text.lower().split()
    return (
        len(tokens) >= 5
        and tokens[0] == "the"
        and tokens[1] == "system"
        and tokens[2] == "shall"
    )


# â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def split_mixed_requirements(
    requirements: List[str],
) -> Dict[str, Dict[str, str]]:
    """
    Split a list of MIXED requirements into FR + NFR pairs.

    Each output requirement begins with "The system shall" so it passes
    req_extractor.py's IEEE filter without modification.

    Return format
    -------------
    {
        "The system shall process payments securely.": {
            "fr":  "The system shall process payments.",
            "nfr": "The system shall ensure that payment processing meets security requirements.",
        },
    }

    On any parse failure, or if the LLM produces a non-IEEE sentence for
    either the FR or NFR, the original MIXED requirement is used as the FR
    and the NFR is omitted (rather than producing corrupt output).  The
    caller in requirement_engine.py handles this gracefully.
    """
    if not requirements:
        return {}

    result: Dict[str, Dict[str, str]] = {}
    chunks = _chunk(requirements, _MAX_BATCH_SIZE)

    for chunk in chunks:
        try:
            splits = await _split_chunk(chunk)

            for idx, orig in enumerate(chunk, 1):
                entry = splits.get(str(idx))

                if not entry or not isinstance(entry, dict):
                    logger.warning(
                        "mixed_split no entry for req index=%d req=%r â€” using original as FR",
                        idx,
                        orig[:60],
                    )
                    result[orig] = {"fr": orig, "nfr": ""}
                    continue

                fr = (entry.get("fr") or "").strip()
                nfr = (entry.get("nfr") or "").strip()

                # Validate both outputs against the IEEE filter before accepting them.
                # If either fails, log it and fall back rather than emitting bad output.
                fr_valid = _is_valid_ieee(fr)
                nfr_valid = _is_valid_ieee(nfr)

                if not fr_valid:
                    logger.warning(
                        "mixed_split FR failed IEEE check fr=%r â€” using original as FR",
                        fr[:80],
                    )
                    fr = orig

                if not nfr_valid:
                    logger.warning(
                        "mixed_split NFR failed IEEE check nfr=%r â€” omitting NFR",
                        nfr[:80],
                    )
                    nfr = ""

                result[orig] = {"fr": fr, "nfr": nfr}

                ClassificationEventLogger.log_mixed_split(
                    requirement_id=orig[:40],
                    status="SUCCESS",
                    fr_text=fr,
                    nfr_text=nfr if nfr else None,
                )

        except Exception as exc:
            logger.error(
                "mixed_split chunk failed (%s) â€” using originals as FR for %d requirements",
                exc,
                len(chunk),
            )
            ClassificationEventLogger.log_mixed_split(
                requirement_id="batch",
                status="ERROR",
                reason=str(exc),
            )
            for req in chunk:
                result[req] = {"fr": req, "nfr": ""}

    return result
