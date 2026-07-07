"""
Batch Classification Service

Classifies requirements as FR, NFR, or MIXED in a single LLM call.

Design constraints
------------------
- System prompt is kept under ~450 tokens so 8b models on free-tier APIs
  Groq retains full rule fidelity across all examples.
- The decision logic uses one structural test only — no keyword lists.
  Keyword lists are hardcoded and break on unseen vocabulary.
  The structural test ("What does the system verb? Does it have a noun answer?")
  is domain-agnostic and works on any future input format.
- Large batches are automatically chunked so the user-prompt never pushes
  the total token count past the model's reliable instruction window.
"""

import logging
from typing import Any, Dict, List

from app.infrastructure.llm.call_llm import call_llm
from app.infrastructure.llm.output_validation import OutputValidationError, guarded_llm_call

logger = logging.getLogger(__name__)

# Maximum requirements per LLM call.
# At ~18 tokens per requirement in the user prompt, 20 items ˜ 360 tokens.
# Combined with the ~420-token system prompt this stays well under 800 tokens total,
# which is the reliable instruction-following ceiling for 8b models on free-tier APIs.
_MAX_BATCH_SIZE = 20

# -- Prompt --------------------------------------------------------------------
#
# Design rationale for length
# ---------------------------
# The system prompt below is intentionally compact.  Every section has a
# clear job and nothing is repeated.  The worked examples are placed
# immediately after the rule they illustrate — not separated by hundreds of
# tokens — so the model never has to retrieve a rule it read earlier.
#
# The single decision test
# ------------------------
# Instead of listing quality-adverb keywords ("securely, reliably, ..."),
# the prompt uses one structural question: "What does the system [verb]?
# Does that question have a concrete noun answer?"
# This is future-proof: it works on any verb, any domain, any writing style.
# A keyword list breaks the moment the author uses a synonym ("robustly",
# "tamper-proof", "fault-tolerant") that was not in the list.

_SYSTEM_PROMPT = """\
You are a requirements classification engine.

CLASSIFICATION RULES
Apply these two steps in order.  Stop as soon as you have an answer.

STEP 1 — Is a system operation present?
Ask: "What does the system [verb]?" 
If that question has a concrete noun as its answer ? operation IS present.
If the question has no noun answer ? operation is NOT present ? classify NFR.

  Operation present:
    "The system shall encrypt customer data." ? encrypts what? ? customer data ?
    "The system shall log administrative actions." ? logs what? ? actions ?
    "The system shall load the product catalog." ? loads what? ? catalog ?

  No operation:
    "The system shall remain available." ? remains what? ? no noun ? ? NFR
    "The system shall support 10,000 users." ? capacity constraint, not action ? ? NFR
    "The system shall maintain response time under 2s." ? property, not action ? ? NFR

STEP 2 — Is a quality constraint also present?
A quality constraint qualifies HOW or HOW WELL the action is performed:
  - An adverb modifying the verb  (securely, immediately, automatically)
  - A time or numeric bound on the action  (within 2 seconds, at least 99.9%)
  - A method that implies a quality standard  (using encryption, via HTTPS)

  Operation + quality constraint ? MIXED
    "The system shall process payments securely." ? action ?, securely ? ? MIXED
    "The system shall confirm transactions immediately." ? action ?, immediately ? ? MIXED
    "The system shall encrypt customer data during storage and transmission."
      ? action ?, "during storage and transmission" = scope constraint on the action ? ? MIXED

  Operation, no quality constraint ? FR
    "The system shall detect unauthorized access attempts." ? action ?, no quality modifier ? FR
    "The system shall send order confirmation emails." ? action ?, no quality modifier ? FR

OUTPUT
Return ONLY valid JSON.  No markdown, no explanation.
{"classifications":{"1":"FR","2":"NFR","3":"MIXED"}}
Use only the values: FR, NFR, MIXED\
"""

_USER_PROMPT_TEMPLATE = """\
Classify each requirement below.

{numbered_list}

Return ONLY:
{{"classifications":{{"1":"...","2":"..."}}}}"""


# -- Token budget --------------------------------------------------------------

def _output_token_budget(count: int) -> int:
    """
    Compute output token budget for a batch of `count` requirements.

    Each classification entry is roughly 8 tokens in JSON
    (e.g. `"12": "MIXED",`).  A 1.5x safety margin handles formatting
    variation.  Hard bounds prevent waste on tiny batches and truncation
    on large ones.
    """
    tokens = int(count * 8 * 1.5)
    return max(80, min(512, tokens))


# -- Chunking ------------------------------------------------------------------

def _chunk(items: List[str], size: int) -> List[List[str]]:
    """Split a list into sublists of at most `size` items."""
    return [items[i : i + size] for i in range(0, len(items), size)]


# -- Core LLM call -------------------------------------------------------------

async def _classify_chunk(
    requirements: List[str],
    model: str | None,
) -> Dict[str, str]:
    """
    Classify one chunk of requirements.

    Returns a dict mapping 1-based string index ? label ("FR"|"NFR"|"MIXED").
    Raises OutputValidationError on parse failure (caller handles fallback).
    """
    numbered = "\n".join(f"{i+1}. {r}" for i, r in enumerate(requirements))
    user_prompt = _USER_PROMPT_TEMPLATE.format(numbered_list=numbered)
    token_budget = _output_token_budget(len(requirements))

    data = await guarded_llm_call(
        lambda prompt, system: call_llm(
            prompt=prompt,
            system_prompt=system,
            model=model,
            num_predict=token_budget,
        ),
        user_prompt,
        _SYSTEM_PROMPT,
        {},
    )

    classifications = data.get("classifications", {})
    if not isinstance(classifications, dict):
        raise OutputValidationError("Missing or invalid 'classifications' object in response")

    return classifications


# -- Public API ----------------------------------------------------------------

async def classify_requirements_batch(
    requirements: List[str],
    model: str | None = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Classify a list of requirements, returning one entry per requirement.

    Large lists are automatically split into chunks of at most _MAX_BATCH_SIZE
    items so the combined system + user prompt never exceeds the model's
    reliable instruction-following window.

    Return format
    -------------
    {
        "The system shall allow users to log in.": {"type": "FR",  "confidence": "HIGH"},
        "Response time shall be under 2 seconds.": {"type": "NFR", "confidence": "HIGH"},
    }

    On any parse failure for a chunk the affected requirements fall back to
    {"type": "ABSTAIN", "confidence": "LOW"} so the pipeline can escalate them
    individually rather than failing the whole batch.
    """
    if not requirements:
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    chunks = _chunk(requirements, _MAX_BATCH_SIZE)

    for chunk in chunks:
        try:
            classifications = await _classify_chunk(chunk, model)

            for i, req in enumerate(chunk, 1):
                label = classifications.get(str(i), "").strip().upper()

                if label not in ("FR", "NFR", "MIXED"):
                    logger.warning(
                        "batch_classify unexpected label=%r for req=%r — marking ABSTAIN",
                        label,
                        req[:60],
                    )
                    result[req] = {"type": "ABSTAIN", "confidence": "LOW"}
                else:
                    result[req] = {"type": label, "confidence": "HIGH"}

        except Exception as exc:
            logger.error(
                "batch_classify chunk failed (%s) — marking %d requirements ABSTAIN",
                exc,
                len(chunk),
            )
            for req in chunk:
                result[req] = {"type": "ABSTAIN", "confidence": "LOW"}

    return result
