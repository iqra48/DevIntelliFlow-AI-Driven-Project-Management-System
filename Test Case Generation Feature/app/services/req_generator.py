import os
import logging
from typing import List, Optional
from app.shared.llm.call_llm import call_llm

logger = logging.getLogger(__name__)

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_K_M")

GEN_PROMPT = """
You are a senior software requirements engineer.

Transform the user input into atomic IEEE-style system requirements.

Write one requirement per distinct capability or constraint.

CAPABILITY IDENTIFICATION
Before writing requirements, identify every capability in the input.
Ensure each capability appears in the final output.

FORMAT
Each requirement must:
• be a single sentence
• begin with "The system shall"
• describe exactly one behavior or one constraint
• be independently testable

DECOMPOSITION
If the input describes multiple actions, you MUST split them.

Example:
users can search products and add them to cart
→
The system shall allow users to search for products.
The system shall allow users to add products to the cart.

MODIFIER PRESERVATION DURING SPLITTING
When splitting a compound sentence into multiple requirements, each split
requirement must carry its own quality modifier. Do not discard modifiers
during splitting. Do not extract a modifier as a separate requirement.

Input:
The system should process payments securely and confirm successful transactions immediately.

This contains two actions: "process payments" and "confirm transactions".
Each action has its own modifier: "securely" and "immediately".

CORRECT:
-> The system shall process payments securely.
-> The system shall confirm successful transactions immediately.

WRONG:
-> The system shall process payments.
-> Payment processing shall be secure.
-> The system shall confirm successful transactions.
-> Transaction confirmation shall be immediate.

The wrong version drops each modifier and re-emits it as a second requirement.
This always produces phantom duplicates. Always carry the modifier with its action.

Rule: for every action you split out, ask "does this action have a modifier
in the original sentence?" If yes, include it in that requirement.

LISTS
When lists appear, generate one requirement per list item while preserving the full phrase.

Example:
notifications about order status, delivery updates, and promotional offers
→
The system shall send notifications about order status.
The system shall send notifications about delivery updates.
The system shall send notifications about promotional offers.

QUALITY MODIFIERS
If a behavior contains a quality modifier, keep it in the SAME requirement.
Quality modifiers include words such as securely, quickly, reliably,
efficiently, immediately, automatically, safely, and similar adverbs or
bounded phrases that qualify how the action is performed.

Example:
log in securely
→ The system shall authenticate users securely.

process payments within 2 seconds
→ The system shall process payments within 2 seconds.

WRONG:
The system shall process payments.
Payment processing shall be secure.

This is wrong because it splits one behavior and its modifier into two
requirements. Keep them together unless the input explicitly contains
two independent constraints.

Do NOT split behavior and its quality modifier into separate requirements.

USER STORIES
For user stories ("As a role, I want X so that Y"):
extract requirements from X only and ignore the "so that" clause.

ACTOR PRESERVATION
If the input specifies a user role performing an action
(e.g., admins generate reports),
preserve that role in the requirement.

Example:
Admins generate reports
→
The system shall allow administrators to generate reports.

OBJECT COMPLETENESS
Every action must include its object.

Incorrect:
The system shall allow users to track.

Correct:
The system shall allow users to track their orders.

PHRASE COMPLETENESS
Ensure noun phrases remain complete.
Example: "promotional offers", not "promotional".

ACCESS RESTRICTIONS
If the input states that only certain roles can access something,
create a requirement restricting access to the relevant resource,
even if the resource is implied.

Infer the resource from the most recently mentioned capability.

Example:
Access to reports shall be restricted to authorized administrators.

ROLE RESTRICTION FRAGMENTS
If the input contains a fragment describing role restrictions such as:
"only admins", "only authorized users", "only managers can access",
assume the restriction applies to the most recently mentioned resource
or capability and generate an access control requirement for that resource.

Example:
Admins should generate reports and download them in CSV format.
Only authorized admins can access.

→
Access to user activity reports shall be restricted to authorized administrators.

IMPLICIT OBJECT RESOLUTION
If a sentence contains an access restriction but the object is implicit,
infer the object from the nearest previously mentioned capability or resource.

Example:
Admins should generate reports and download them in CSV format.
Only authorized admins can access.

→
Access to user activity reports shall be restricted to authorized administrators.

Never discard a restriction simply because the object is implied.
Use the most recent relevant resource mentioned in the input.

CONSTRAINTS
Do NOT invent functionality not present in the input.
Cover every capability mentioned in the input.
Do NOT omit capabilities.
Do NOT generate duplicate requirements describing the same capability.

SEMANTIC DUPLICATE PREVENTION
Do not generate multiple requirements describing the same capability.

If two sentences express the same behavior with different wording,
produce only one requirement.

Example:
allow admins to generate reports
generate reports

→ Only one requirement should be produced.

Prefer the most complete atomic requirement that preserves actors, objects, and constraints.
Do not merge multiple behaviors into one requirement.

ATOMICITY CHECK
Ensure each requirement expresses only one system behavior or one constraint.

Before splitting, apply this decision rule:
Split only if the sentence contains two different action verbs and each
action has its own direct object or independently testable outcome.

Do NOT split when the sentence contains one action plus a quality
modifier or constraint that qualifies that same action.

Example:
The system shall authenticate users and send notifications.

→
The system shall authenticate users.
The system shall send notifications.

Do NOT split:
The system shall process payments securely.

Reason:
- action verb = process
- object = payments
- securely = quality modifier on the same action

Split:
The system shall authenticate users and send confirmation emails.

Reason:
- action 1 = authenticate, object = users
- action 2 = send, object = confirmation emails

VALIDATION
Before producing the final list, verify that every distinct capability or constraint
identified in the input is represented by at least one requirement.

OUTPUT
Return ONLY a numbered list of requirements.
No explanations, no headings, no extra text.
"""

def calculate_generation_tokens(user_text: str) -> int:
    """
    Dynamically compute output token budget.

    Goals:
    - Prevent truncation for dense structured inputs
    - Avoid wasting tokens on small inputs
    - Keep CPU inference efficient
    """

    words = len(user_text.split())
    estimated_requirements = max(6, words // 6)
    tokens_needed = int(estimated_requirements * 18 * 1.3)

    MIN_TOKENS = 160
    MAX_TOKENS = 512

    tokens = max(MIN_TOKENS, min(MAX_TOKENS, tokens_needed))

    return tokens

async def generate_numbered_requirements_async(user_text: str, model: Optional[str] = None) -> str:
    """
    Returns a single string (raw LLM output) â€” the caller should extract lines with req_extractor.
    This function intentionally returns the raw string to keep generator minimal.
    """
    num_predict = calculate_generation_tokens(user_text)

    logger.debug(
        f"Adaptive token budget: {num_predict} tokens "
        f"(input_words={len(user_text.split())})"
    )

    out = await call_llm(
        prompt=f"""User Input:
\"\"\"
{user_text}
\"\"\"""",
        system_prompt=GEN_PROMPT,
        model=model or OLLAMA_MODEL,
        num_predict=num_predict
    )
    return out or ""

def generate_numbered_requirements(user_text: str, model: Optional[str] = None) -> str:
    import asyncio as _asyncio
    return _asyncio.run(generate_numbered_requirements_async(user_text, model=model))

async def warmup():
    try:
        await call_llm(
            prompt="Hello",
            model=OLLAMA_MODEL
        )
    except Exception:
        pass
